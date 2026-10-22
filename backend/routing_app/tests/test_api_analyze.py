"""/api/analyze end to end with mocked providers: no network calls."""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from django.test import Client

from routing_app.geo import LatLon
from routing_app.providers.http import ProviderError
from routing_app.providers.types import RawRoute, RouteRequest
from routing_app.providers.weather import Forecast, HourValues
from routing_app.services import analyze as analyze_module

from .helpers import line, raw_route

pytestmark = pytest.mark.django_db(transaction=True)

ORIGIN, DEST = (35.0, -100.0), (35.0, -95.0)
NORTH = raw_route(line(ORIGIN, (36.5, -97.5)) + line((36.5, -97.5), DEST)[1:], 6 * 3600)
STRAIGHT = raw_route(line(ORIGIN, DEST), 5 * 3600)
SOUTH = raw_route(line(ORIGIN, (33.5, -97.5)) + line((33.5, -97.5), DEST)[1:], 6.5 * 3600)


class FakeProvider:
    name = "fake"
    is_truck_profile = True

    def __init__(self, routes: list[RawRoute]):
        self._routes = routes

    async def routes(self, client: httpx.AsyncClient, req: RouteRequest, via: LatLon | None = None):
        if via is not None:
            raise ProviderError(self.name, "no_route", "no via")
        return self._routes


def storm_on_straight_line(points: list[LatLon]) -> list[Forecast]:
    """47 mph wind within ~0.1° of lat 35 (the straight route); calm everywhere else."""

    def at(p: LatLon) -> Forecast:
        windy = abs(p[0] - 35.0) < 0.1 and -99.0 < p[1] < -96.0
        base = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
        values = HourValues(47.0 if windy else 8.0, 60.0 if windy else 12.0, 0.0, 0.0)
        return {base + timedelta(hours=h): values for h in range(72)}

    return [at(p) for p in points]


@pytest.fixture
def fake_world(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        analyze_module, "configured_providers", lambda: [FakeProvider([STRAIGHT, NORTH, SOUTH])]
    )

    async def fake_fetch(client: Any, points: list[LatLon], start: datetime, end: datetime):
        return storm_on_straight_line(points)

    monkeypatch.setattr(analyze_module, "fetch_forecasts", fake_fetch)


def body(**overrides: Any) -> dict[str, Any]:
    departure = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    return {
        "origin": {"lat": ORIGIN[0], "lon": ORIGIN[1], "label": "Origin"},
        "destination": {"lat": DEST[0], "lon": DEST[1], "label": "Destination"},
        "departure_time": departure,
        "load_lbs": 36_000,
        "interval_miles": 25,
        **overrides,
    }


def post(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    response = Client().post("/api/analyze", payload, content_type="application/json")
    return response.status_code, response.json()


def test_analyze_ranks_storm_route_last_and_explains_why(fake_world: None) -> None:
    status, data = post(body())
    assert status == 200, data
    assert [r["name"] for r in data["routes"]] == ["Route A", "Route B", "Route C"]

    straight = data["routes"][0]
    # 47 mph + 36,000 lb trips the load rule on the straight route.
    assert straight["summary"]["no_travel_miles"] > 0
    assert any("load rule" in cp["reason"] for cp in straight["checkpoints"])
    assert data["recommended_route_id"] == "B"  # Calm and faster than C.
    assert data["ranking"][-1] == "A"
    assert data["recommendation_reason"].startswith("Route B: 0 No Travel miles (Route A has")
    assert data["no_safe_route"] is False

    stored = analyze_module.cache.get(f"analysis:{data['analysis_id']}")
    assert stored["load_lbs"] == 36_000 and len(stored["routes"]) == 3


def test_analyze_response_shape_and_invariants(fake_world: None) -> None:
    _, data = post(body(interval_miles=10))
    for route in data["routes"]:
        cps = route["checkpoints"]
        assert cps[0]["mile"] == 0
        assert cps[-1]["mile"] == pytest.approx(route["distance_mi"], abs=0.1)
        assert all(b["mile"] - a["mile"] <= 10.05 for a, b in zip(cps, cps[1:], strict=False))
        etas = [datetime.fromisoformat(cp["eta"]) for cp in cps]
        assert etas == sorted(etas)
        assert etas[0] == datetime.fromisoformat(data["departure_time"])
        s = route["summary"]
        level_miles = sum(
            s[f"{k}_miles"] for k in ("no_travel", "severe", "high", "moderate", "low")
        )
        assert level_miles == pytest.approx(route["distance_mi"], abs=0.3)
        segs = route["segments"]
        assert segs[0]["from_mile"] == 0
        assert segs[-1]["to_mile"] == pytest.approx(route["distance_mi"], abs=0.1)
        coords = route["geometry"]["coordinates"]
        assert len(coords) <= 2000
        assert len(route["geometry_miles"]) == len(route["geometry_elapsed_s"]) == len(coords)
        assert coords[0] == [ORIGIN[1], ORIGIN[0]]  # GeoJSON order: [lon, lat].


def test_departure_is_normalised_to_utc(fake_world: None) -> None:
    local = (datetime.now(UTC) + timedelta(hours=2)).astimezone(
        __import__("datetime").timezone(timedelta(hours=-5))
    )
    _, data = post(body(departure_time=local.isoformat()))
    assert data["departure_time"].endswith("Z")


def test_overweight_load_is_accepted_with_warning(fake_world: None) -> None:
    status, data = post(body(load_lbs=95_000))
    assert status == 200
    assert any("80,000 lb" in w for w in data["warnings"])


@pytest.mark.parametrize(
    ("overrides", "code", "fragment"),
    [
        ({"interval_miles": 30}, "validation_error", "interval_miles"),
        ({"load_lbs": 0}, "validation_error", "load_lbs"),
        ({"load_lbs": 250_000}, "validation_error", "load_lbs"),
        ({"departure_time": "2026-10-23T14:00:00"}, "validation_error", "UTC offset"),
        ({"departure_time": "tomorrow"}, "validation_error", "ISO 8601"),
        ({"origin": {"lat": 95, "lon": 0}}, "validation_error", "lat"),
        ({"destination": {"lat": 35.0, "lon": -100.001}}, "validation_error", "1 mile apart"),
        (
            {"departure_time": (datetime.now(UTC) - timedelta(hours=1)).isoformat()},
            "departure_in_past",
            "past",
        ),
        (
            {"departure_time": (datetime.now(UTC) + timedelta(days=20)).isoformat()},
            "beyond_forecast_horizon",
            "16-day",
        ),
    ],
)
def test_invalid_requests_return_uniform_400(
    fake_world: None, overrides: dict[str, Any], code: str, fragment: str
) -> None:
    status, data = post(body(**overrides))
    assert status == 400
    assert data["error"]["code"] == code
    assert fragment in data["error"]["message"]


def test_departure_within_grace_period_is_accepted(fake_world: None) -> None:
    status, _ = post(body(departure_time=(datetime.now(UTC) - timedelta(minutes=10)).isoformat()))
    assert status == 200


def test_trip_ending_past_horizon_is_rejected(
    fake_world: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        analyze_module, "horizon_end", lambda now=None: datetime.now(UTC) + timedelta(hours=3)
    )
    status, data = post(body())
    assert status == 400
    assert data["error"]["code"] == "beyond_forecast_horizon"


def test_no_route_maps_to_422(monkeypatch: pytest.MonkeyPatch) -> None:
    class NoRoute(FakeProvider):
        async def routes(self, client: Any, req: Any, via: Any = None):
            raise ProviderError("fake", "no_route", "no route")

    monkeypatch.setattr(analyze_module, "configured_providers", lambda: [NoRoute([])])
    status, data = post(body())
    assert status == 422
    assert data["error"]["code"] == "upstream_no_route"


def test_forecast_gap_is_reported_not_treated_as_calm(
    fake_world: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def gappy(client: Any, points: list[LatLon], start: datetime, end: datetime):
        return [{} for _ in points]

    monkeypatch.setattr(analyze_module, "fetch_forecasts", gappy)
    status, data = post(body())
    assert status == 422
    assert data["error"]["code"] == "forecast_unavailable"
