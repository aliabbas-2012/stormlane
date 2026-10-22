import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from routing_app.geo import cumulative_miles, encode_polyline
from routing_app.providers.routing import (
    OsrmProvider,
    TomTomProvider,
    parse_osrm_route,
    parse_tomtom_route,
)
from routing_app.providers.types import RouteRequest

from .helpers import mock_client

REQ = RouteRequest(
    (32.78, -96.80), (39.74, -104.99), datetime(2026, 10, 23, 15, tzinfo=UTC), 38_000
)
POINTS = [(0.0, 0.0), (0.0, 1.0), (0.0, 2.0)]


def osrm_route(durations: list[list[float]], total: float) -> dict:
    return {
        "geometry": encode_polyline(POINTS, 6),
        "distance": 222_000.0,
        "duration": total,
        "legs": [{"annotation": {"duration": d}} for d in durations],
    }


def test_osrm_segment_durations_across_legs_are_rescaled_to_route_total() -> None:
    route = parse_osrm_route(osrm_route([[10.0], [30.0]], total=44.0))
    assert route.timing_source == "segments"
    assert route.cum_seconds == pytest.approx([0, 11, 44])


def test_osrm_falls_back_to_proportional_timing_on_mismatch() -> None:
    route = parse_osrm_route(osrm_route([[10.0]], total=40.0))  # 1 duration for 2 segments.
    assert route.timing_source == "proportional"
    assert route.cum_seconds == pytest.approx([0, 20, 40])


@pytest.mark.parametrize("via", [None, (36.0, -101.0)])
def test_osrm_request_shape(via: tuple[float, float] | None) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"code": "Ok", "routes": [osrm_route([[1.0, 1.0]], 2.0)]})

    async def go() -> None:
        async with mock_client(handler) as client:
            routes = await OsrmProvider().routes(client, REQ, via=via)
            assert routes[0].synthesized is (via is not None)

    asyncio.run(go())
    request = seen[0]
    coords = request.url.path.rsplit("/", 1)[-1].split(";")
    assert coords[0] == "-96.800000,32.780000"  # OSRM wants lon,lat.
    assert len(coords) == (3 if via else 2)
    assert request.url.params["alternatives"] == ("false" if via else "2")
    assert request.url.params["annotations"] == "duration,distance"


def tomtom_route(progress: list[dict]) -> dict:
    return {
        "summary": {"lengthInMeters": 222_000, "travelTimeInSeconds": 100},
        "legs": [{"points": [{"latitude": a, "longitude": b} for a, b in POINTS]}],
        "progress": progress,
    }


def test_tomtom_sparse_progress_is_interpolated_by_distance() -> None:
    route = parse_tomtom_route(
        tomtom_route(
            [
                {"pointIndex": 0, "travelTimeInSeconds": 0},
                {"pointIndex": 2, "travelTimeInSeconds": 100},
            ]
        )
    )
    assert route.timing_source == "segments"
    cum = cumulative_miles(POINTS)
    assert route.cum_seconds[1] == pytest.approx(100 * cum[1] / cum[2])


def test_tomtom_without_progress_uses_proportional_timing() -> None:
    assert parse_tomtom_route(tomtom_route([])).timing_source == "proportional"


def test_tomtom_request_uses_truck_parameters() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"routes": [tomtom_route([])]})

    async def go() -> None:
        async with mock_client(handler) as client:
            await TomTomProvider("k").routes(client, REQ)

    asyncio.run(go())
    params = seen[0].url.params
    assert "32.780000,-96.800000:39.740000,-104.990000" in seen[0].url.path
    assert params["travelMode"] == "truck"
    assert params["vehicleCommercial"] == "true"
    assert params["vehicleWeight"] == "17237"  # 38,000 lb in kg.
    assert params["maxAlternatives"] == "2"
    assert params["departAt"] == "2026-10-23T15:00:00+00:00"
    assert params["extendedRouteRepresentation"] == "travelTime"
