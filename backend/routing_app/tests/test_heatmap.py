from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.core.cache import cache
from django.test import Client

from routing_app.geo import LatLon
from routing_app.providers.weather import Forecast, HourValues
from routing_app.services import heatmap as heatmap_module

from .helpers import line

ANALYSIS_ID = "a" * 32
DEPARTURE = (datetime.now(UTC) + timedelta(hours=1)).replace(minute=30, second=0, microsecond=0)
START = DEPARTURE.replace(minute=0)


def store_analysis(load_lbs: float = 36_000) -> None:
    route = [[lon, lat] for lat, lon in line((35.0, -100.0), (35.0, -98.0), 20)]
    cache.set(
        f"analysis:{ANALYSIS_ID}",
        {
            "departure": DEPARTURE,
            "load_lbs": load_lbs,
            "routes": [{"id": "A", "coordinates": route}],
        },
    )


def windy_after_six_hours(points: list[LatLon]) -> list[Forecast]:
    """47 mph wind from +6 h onwards, rain only in the bucket stamped +3 h, a gap at +40 h."""
    forecast: Forecast = {}
    for h in range(-1, 52):
        hour = START + timedelta(hours=h)
        forecast[hour] = HourValues(
            wind_mph=47.0 if h >= 6 else 10.0,
            gust_mph=55.0,
            rain_in=0.3 if h == 3 else 0.0,
            snow_in=0.0,
        )
    forecast[START + timedelta(hours=40)] = None
    return [forecast for _ in points]


@pytest.fixture
def fake_weather(monkeypatch: pytest.MonkeyPatch) -> list[tuple[datetime, datetime]]:
    calls: list[tuple[datetime, datetime]] = []

    async def fake(client: Any, points: list[LatLon], start: datetime, end: datetime):
        calls.append((start, end))
        return windy_after_six_hours(points)

    monkeypatch.setattr(heatmap_module, "fetch_forecasts", fake)
    return calls


def post(analysis_id: str = ANALYSIS_ID) -> tuple[int, dict[str, Any]]:
    response = Client().post(
        "/api/heatmap", {"analysis_id": analysis_id}, content_type="application/json"
    )
    return response.status_code, response.json()


def test_columnar_payload_shape(fake_weather: list) -> None:
    store_analysis()
    status, data = post()
    assert status == 200
    n = len(data["points"])
    assert n > 0
    assert len(data["hours"]) == 49
    assert data["hours"][0] == START.isoformat().replace("+00:00", "Z")
    for key in ("risk", "wind", "rain", "snow"):
        assert len(data[key]) == n
        assert all(len(row) == 49 for row in data[key])
    lon, lat = data["points"][0]
    assert -101 < lon < -97 and 34 < lat < 36  # [lon, lat] order
    assert fake_weather[0][0] == START


def test_uses_the_risk_engine_with_load_rules(fake_weather: list) -> None:
    store_analysis(load_lbs=36_000)
    _, data = post()
    row = data["risk"][0]
    assert row[0] == 0  # 10 mph, no rain
    assert row[2] == 2  # bucket stamped +3 h (0.30 in) covers hour +2 → High
    assert row[3] == 0
    assert row[6] == 4  # 47 mph + 36,000 lb → No Travel via load rule
    assert data["wind"][0][6] == 47.0


def test_light_load_does_not_trigger_load_rule(fake_weather: list) -> None:
    store_analysis(load_lbs=20_000)
    _, data = post()
    assert data["risk"][0][6] == 3  # 47 mph alone is Severe


def test_model_gaps_are_marked_no_data(fake_weather: list) -> None:
    store_analysis()
    _, data = post()
    assert data["risk"][0][40] == heatmap_module.NO_DATA
    assert data["risk"][0][39] == heatmap_module.NO_DATA  # its precipitation bucket is +40 h


def test_result_is_cached(fake_weather: list) -> None:
    store_analysis()
    post()
    post()
    assert len(fake_weather) == 1


def test_unknown_analysis_is_404() -> None:
    status, data = post("b" * 32)
    assert status == 404
    assert data["error"]["code"] == "analysis_not_found"


def test_malformed_id_is_400() -> None:
    status, data = post("not-an-id")
    assert status == 400
    assert data["error"]["code"] == "validation_error"
