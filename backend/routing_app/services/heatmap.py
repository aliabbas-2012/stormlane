"""POST /api/heatmap: hourly risk over the trip corridor for departure .. +48 h.

The payload is columnar (one array per variable, one row per point) because the browser
builds a single GeoJSON source from it once and then only changes paint properties."""

from datetime import UTC, datetime, timedelta
from typing import Any

from django.core.cache import cache

from routing_app.geo import floor_to_hour
from routing_app.geo.corridor import corridor_grid
from routing_app.providers.http import make_client
from routing_app.providers.weather import fetch_forecasts, horizon_end
from routing_app.risk import classify_conditions

from .analyze import iso
from .errors import ServiceError

HOURS = 49  # +0 h .. +48 h inclusive
CACHE_TTL_S = 30 * 60
NO_DATA = -1  # Risk value for a point/hour the model has no data for.


def _round(value: float) -> float:
    return round(value, 2)


async def build_heatmap(analysis_id: str, now: datetime | None = None) -> dict[str, Any]:
    cache_key = f"heatmap:{analysis_id}"
    cached = await cache.aget(cache_key)
    if cached is not None:
        return cached

    analysis = await cache.aget(f"analysis:{analysis_id}")
    if analysis is None:
        raise ServiceError(
            "analysis_not_found",
            "This analysis has expired. Run the analysis again to load the heatmap.",
            http_status=404,
        )

    departure: datetime = analysis["departure"]
    load_lbs: float = analysis["load_lbs"]
    start = floor_to_hour(departure)
    hours = [start + timedelta(hours=h) for h in range(HOURS)]
    # Clip to the forecast horizon instead of failing: the routes themselves are valid.
    last = min(hours[-1] + timedelta(hours=1), horizon_end(now or datetime.now(UTC)))

    routes = [[(lat, lon) for lon, lat in r["coordinates"]] for r in analysis["routes"]]
    points, cell_deg = corridor_grid(routes)

    async with make_client() as client:
        forecasts = await fetch_forecasts(client, points, start, last)

    risk, wind, rain, snow = [], [], [], []
    for forecast in forecasts:
        r_row, w_row, p_row, s_row = [], [], [], []
        for hour in hours:
            # Same convention as checkpoints: instantaneous wind at the hour, precipitation
            # from the bucket that covers it (stamped one hour later).
            instant = forecast.get(hour)
            accumulated = forecast.get(hour + timedelta(hours=1))
            if instant is None or accumulated is None:
                r_row.append(NO_DATA)
                w_row.append(0.0)
                p_row.append(0.0)
                s_row.append(0.0)
                continue
            result = classify_conditions(
                instant.wind_mph, accumulated.rain_in, accumulated.snow_in, load_lbs
            )
            r_row.append(int(result.level))
            w_row.append(_round(instant.wind_mph))
            p_row.append(_round(accumulated.rain_in))
            s_row.append(_round(accumulated.snow_in))
        risk.append(r_row)
        wind.append(w_row)
        rain.append(p_row)
        snow.append(s_row)

    payload = {
        "analysis_id": analysis_id,
        "cell_deg": round(cell_deg, 4),
        "points": [[round(lon, 4), round(lat, 4)] for lat, lon in points],
        "hours": [iso(h) for h in hours],
        "risk": risk,
        "wind": wind,
        "rain": rain,
        "snow": snow,
    }
    await cache.aset(cache_key, payload, CACHE_TTL_S)
    return payload
