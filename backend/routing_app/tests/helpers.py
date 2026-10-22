"""Builders shared by provider/service tests."""

from collections.abc import Callable

import httpx

from routing_app.geo import cumulative_miles, proportional_cumulative_seconds
from routing_app.providers.types import RawRoute

Handler = Callable[[httpx.Request], httpx.Response]


def mock_client(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def line(
    start: tuple[float, float], end: tuple[float, float], n: int = 50
) -> list[tuple[float, float]]:
    return [
        (start[0] + (end[0] - start[0]) * i / n, start[1] + (end[1] - start[1]) * i / n)
        for i in range(n + 1)
    ]


def raw_route(
    points: list[tuple[float, float]], duration_s: float, provider: str = "fake"
) -> RawRoute:
    cum = cumulative_miles(points)
    return RawRoute(
        points=points,
        cum_seconds=proportional_cumulative_seconds(cum, duration_s),
        distance_m=cum[-1] * 1609.344,
        duration_s=duration_s,
        provider=provider,
        timing_source="proportional",
    )
