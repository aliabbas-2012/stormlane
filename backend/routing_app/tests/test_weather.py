import asyncio
from datetime import UTC, datetime

import httpx

from routing_app.providers.weather import HourValues, fetch_forecasts

START = datetime(2026, 10, 23, 22, tzinfo=UTC)
END = datetime(2026, 10, 24, 1, tzinfo=UTC)  # Spans two UTC days.


def _block(n_hours: int = 48) -> dict:
    times = [f"2026-10-{23 + h // 24}T{h % 24:02d}:00" for h in range(n_hours)]
    return {
        "hourly": {
            "time": times,
            "wind_speed_10m": [None if h == 47 else 30.0 for h in range(n_hours)],
            "wind_gusts_10m": [40.0] * n_hours,
            "rain": [0.06] * n_hours,
            "showers": [0.04] * n_hours,
            "snowfall": [0.5] * n_hours,
        }
    }


def _fetch(
    points: list[tuple[float, float]], single: bool = False
) -> tuple[list, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        n = len(request.url.params["latitude"].split(","))
        return httpx.Response(200, json=_block() if single else [_block() for _ in range(n)])

    async def go() -> list:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            first = await fetch_forecasts(client, points, START, END)
            second = await fetch_forecasts(client, points, START, END)
            assert first == second
            return first

    return asyncio.run(go()), seen


def test_batches_points_and_combines_rain_with_showers() -> None:
    forecasts, seen = _fetch([(39.1, -104.1), (40.2, -105.2)])
    assert len(seen) == 1  # One batched request, then served from cache.
    params = seen[0].url.params
    assert params["latitude"] == "39.10,40.20"
    assert params["precipitation_unit"] == "inch"
    assert params["wind_speed_unit"] == "mph"
    assert (params["start_date"], params["end_date"]) == ("2026-10-23", "2026-10-24")
    values = forecasts[0][datetime(2026, 10, 23, 22, tzinfo=UTC)]
    assert values == HourValues(wind_mph=30.0, gust_mph=40.0, rain_in=0.1, snow_in=0.5)


def test_missing_model_values_are_marked_as_gaps() -> None:
    forecasts, _ = _fetch([(39.1, -104.1)], single=True)
    assert forecasts[0][datetime(2026, 10, 24, 23, tzinfo=UTC)] is None


def test_nearby_points_share_one_location() -> None:
    forecasts, seen = _fetch([(39.101, -104.101), (39.104, -104.099)], single=True)
    assert seen[0].url.params["latitude"] == "39.10"
    assert forecasts[0] == forecasts[1]
