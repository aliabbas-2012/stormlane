"""Open-Meteo hourly forecasts, batched across many locations per request.

Verified against the live API and docs (2026-10-22):
- With precipitation_unit=inch, snowfall is returned in inches (hourly_units.snowfall == "inch").
- rain/showers/snowfall are *preceding-hour sums*; wind_speed_10m is instantaneous.
- Several comma-separated coordinates return a JSON list (a single one returns an object).
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from routing_app.geo import LatLon

from . import forecast_cache
from .http import ProviderError, get_json

PROVIDER = "open-meteo"
URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARS = ("wind_speed_10m", "wind_gusts_10m", "rain", "showers", "snowfall")
FORECAST_HORIZON_DAYS = 16
CHUNK_SIZE = 100  # Locations per request; keeps URLs ~2 KB.
MAX_CONCURRENT_REQUESTS = 3
CACHE_TTL_S = 30 * 60
# Cache granularity: one entry per rounded location (~1 km) per UTC day.
COORD_DECIMALS = 2


@dataclass(frozen=True, slots=True)
class HourValues:
    wind_mph: float
    gust_mph: float
    rain_in: float  # rain + showers, preceding-hour sum
    snow_in: float  # preceding-hour sum


# Per location: hour (UTC, on the hour) -> values. None marks a gap in the model output.
Forecast = dict[datetime, HourValues | None]


def round_point(p: LatLon) -> LatLon:
    return round(p[0], COORD_DECIMALS), round(p[1], COORD_DECIMALS)


def _cache_key(p: LatLon, day: date) -> str:
    return f"om:{p[0]:.{COORD_DECIMALS}f}:{p[1]:.{COORD_DECIMALS}f}:{day.isoformat()}"


def _days(start: datetime, end: datetime) -> list[date]:
    first, last = start.date(), end.date()
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def horizon_end(now: datetime | None = None) -> datetime:
    """Last hour Open-Meteo can forecast (start of today UTC + 16 days, exclusive)."""
    now = now or datetime.now(UTC)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return today + timedelta(days=FORECAST_HORIZON_DAYS) - timedelta(hours=1)


def parse_location(block: dict[str, Any]) -> dict[date, dict[str, Any]]:
    """Split one location's hourly block into per-UTC-day chunks (the cache unit), with values
    as JSON-friendly [wind, gust, rain, snow] lists (None for a model gap)."""
    hourly = block["hourly"]
    days: dict[date, dict[str, Any]] = {}
    for i, stamp in enumerate(hourly["time"]):
        hour = datetime.fromisoformat(stamp).replace(tzinfo=UTC)
        values = [hourly[v][i] for v in HOURLY_VARS]
        entry = None
        if values[0] is not None:
            wind, gust, rain, showers, snow = values
            entry = HourValues(
                wind_mph=float(wind),
                gust_mph=float(gust or 0.0),
                rain_in=float(rain or 0.0) + float(showers or 0.0),
                snow_in=float(snow or 0.0),
            )
        days.setdefault(hour.date(), {})[hour.isoformat()] = entry and [
            entry.wind_mph,
            entry.gust_mph,
            entry.rain_in,
            entry.snow_in,
        ]
    return days


async def _fetch_chunk(
    client: httpx.AsyncClient, points: list[LatLon], start_day: date, end_day: date
) -> list[dict[date, dict[str, Any]]]:
    params = {
        "latitude": ",".join(f"{p[0]:.{COORD_DECIMALS}f}" for p in points),
        "longitude": ",".join(f"{p[1]:.{COORD_DECIMALS}f}" for p in points),
        "hourly": ",".join(HOURLY_VARS),
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "UTC",
        "start_date": start_day.isoformat(),
        "end_date": end_day.isoformat(),
    }
    data = await get_json(client, PROVIDER, URL, params)
    if isinstance(data, dict) and data.get("error"):
        raise ProviderError(PROVIDER, "bad_response", str(data.get("reason", "error")))
    blocks = data if isinstance(data, list) else [data]
    if len(blocks) != len(points):
        raise ProviderError(PROVIDER, "bad_response", "location count mismatch")
    return [parse_location(b) for b in blocks]


async def fetch_forecasts(
    client: httpx.AsyncClient, points: list[LatLon], start: datetime, end: datetime
) -> list[Forecast]:
    """Hourly forecasts covering [start, end] (UTC) for each point, in input order.

    Points are rounded to ~1 km, deduplicated, and served from cache per (point, UTC day);
    only missing points are fetched, in concurrent chunks of CHUNK_SIZE locations."""
    days = _days(start, end)
    rounded = [round_point(p) for p in points]
    unique = list(dict.fromkeys(rounded))

    keys = {(p, d): _cache_key(p, d) for p in unique for d in days}
    cached = await forecast_cache.load(list(keys.values()))
    missing = [p for p in unique if any(keys[(p, d)] not in cached for d in days)]

    if missing:
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        async def run(chunk: list[LatLon]) -> list[dict[date, dict[str, Any]]]:
            async with semaphore:
                return await _fetch_chunk(client, chunk, days[0], days[-1])

        chunks = [missing[i : i + CHUNK_SIZE] for i in range(0, len(missing), CHUNK_SIZE)]
        results = await asyncio.gather(*(run(c) for c in chunks))
        fresh: dict[str, Any] = {}
        for chunk, parsed in zip(chunks, results, strict=True):
            for p, by_day in zip(chunk, parsed, strict=True):
                for d in days:
                    fresh[keys[(p, d)]] = by_day.get(d, {})
        await forecast_cache.store(fresh, CACHE_TTL_S)
        cached.update(fresh)

    by_point: dict[LatLon, Forecast] = {}
    for p in unique:
        forecast: Forecast = {}
        for d in days:
            for stamp, values in cached[keys[(p, d)]].items():
                forecast[datetime.fromisoformat(stamp)] = values and HourValues(*values)
        by_point[p] = forecast
    return [by_point[p] for p in rounded]
