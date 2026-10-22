import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from routing_app.geo import LatLon
from routing_app.providers.http import ProviderError
from routing_app.providers.types import RawRoute, RouteRequest
from routing_app.services.route_options import RouteOptions, get_route_options

from .helpers import line, raw_route

ORIGIN, DEST = (35.0, -100.0), (35.0, -95.0)
REQ = RouteRequest(ORIGIN, DEST, datetime(2026, 10, 23, 15, tzinfo=UTC), 38_000)
STRAIGHT = raw_route(line(ORIGIN, DEST), 10 * 3600)


def bent(lat: float, hours: float) -> RawRoute:
    """A route bowed through (lat, -97.5): distinct from STRAIGHT when lat is far enough off."""
    return raw_route(line(ORIGIN, (lat, -97.5)) + line((lat, -97.5), DEST)[1:], hours * 3600)


class FakeProvider:
    is_truck_profile = True

    def __init__(self, base: list[RawRoute], via: list[RawRoute] | None = None, name: str = "fake"):
        self.name = name
        self.base = base
        self.via = list(via or [])
        self.via_points: list[LatLon] = []

    async def routes(
        self, client: httpx.AsyncClient, req: RouteRequest, via: LatLon | None = None
    ) -> list[RawRoute]:
        if via is None:
            return self.base
        self.via_points.append(via)
        if not self.via:
            raise ProviderError(self.name, "no_route", "unroutable via point")
        return [self.via.pop(0)]


class FailingProvider(FakeProvider):
    async def routes(self, client: httpx.AsyncClient, req: RouteRequest, via: LatLon | None = None):
        raise ProviderError(self.name, "unavailable", "down")


def run(*providers: FakeProvider) -> RouteOptions:
    async def go() -> RouteOptions:
        async with httpx.AsyncClient() as client:
            return await get_route_options(client, list(providers), REQ)

    return asyncio.run(go())


def test_three_distinct_provider_routes_need_no_via_requests() -> None:
    provider = FakeProvider([STRAIGHT, bent(36.0, 11), bent(34.0, 11)])
    options = run(provider)
    assert len(options.routes) == 3
    assert provider.via_points == []
    assert options.warnings == []


def test_missing_alternatives_are_synthesized_with_small_offsets_first() -> None:
    provider = FakeProvider([STRAIGHT], via=[bent(35.8, 11), bent(34.2, 11)])
    options = run(provider)
    assert len(options.routes) == 3
    assert len(provider.via_points) == 2  # Only the ±15% round was needed.
    assert provider.via_points[0][0] > 35 > provider.via_points[1][0]


def test_near_duplicate_candidates_are_dropped() -> None:
    almost_straight = raw_route(line((35.001, -100.0), (35.001, -95.0)), 10.2 * 3600)
    provider = FakeProvider([STRAIGHT, almost_straight], via=[bent(36.0, 11)] * 4)
    options = run(provider)
    assert len(options.routes) == 2  # STRAIGHT + first bent; repeats of bent are duplicates.
    assert "Only 2 distinct route(s)" in options.warnings[0]


def test_detours_over_1_5x_the_fastest_are_rejected() -> None:
    provider = FakeProvider(
        [STRAIGHT], via=[bent(37.0, 15.1), bent(33.0, 14.9)] + [bent(36.0, 20)] * 2
    )
    options = run(provider)
    assert [round(r.duration_s / 3600, 1) for r in options.routes] == [10.0, 14.9]


def test_unroutable_via_points_are_tolerated() -> None:
    options = run(FakeProvider([STRAIGHT], via=[]))
    assert len(options.routes) == 1


def test_falls_back_to_next_provider_with_warning() -> None:
    options = run(
        FailingProvider([], name="tomtom"),
        FakeProvider([STRAIGHT, bent(36, 11), bent(34, 11)], name="osrm"),
    )
    assert options.provider == "osrm"
    assert "tomtom" in options.warnings[0]


def test_all_providers_failing_raises() -> None:
    with pytest.raises(ProviderError) as exc:
        run(FailingProvider([], name="a"), FailingProvider([], name="b"))
    assert exc.value.code == "unavailable"


def test_results_are_cached() -> None:
    provider = FakeProvider([STRAIGHT, bent(36.0, 11), bent(34.0, 11)])
    first = run(provider)
    provider.base = []  # Would break if called again.
    assert len(run(provider).routes) == len(first.routes)
