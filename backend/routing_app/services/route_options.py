"""Up to 3 distinct, sensible route options.

1. Ask the provider for its best route plus alternatives.
2. If fewer than 3 distinct routes come back, synthesize more through via waypoints offset
   perpendicular to the origin->destination line (±15% of straight-line distance, then ±30%).
3. Reject detours slower than 1.5x the fastest route, and near-duplicates (> 85% of sampled
   points within 1 km of an already accepted route).
If only 1-2 survive, we return those with a warning rather than padding with absurd routes.
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field

import httpx
from django.core.cache import cache

from routing_app.geo import VIA_OFFSET_ROUNDS, RouteIndex, overlap_fraction, perpendicular_via_point
from routing_app.providers.http import ProviderError
from routing_app.providers.routing import RoutingProvider
from routing_app.providers.types import RawRoute, RouteRequest

logger = logging.getLogger(__name__)

TARGET_ROUTES = 3
MAX_DURATION_RATIO = 1.5
OVERLAP_RADIUS_KM = 1.0
MAX_OVERLAP = 0.85
CACHE_TTL_S = 15 * 60


@dataclass
class RouteOptions:
    routes: list[RawRoute]
    provider: str
    is_truck_profile: bool
    warnings: list[str] = field(default_factory=list)


class _Selector:
    """Accepts candidates in preference order, enforcing the duration cap and dedupe."""

    def __init__(self) -> None:
        self.accepted: list[RawRoute] = []
        self._indexes: list[RouteIndex] = []
        self.rejected_slow = 0

    @property
    def full(self) -> bool:
        return len(self.accepted) >= TARGET_ROUTES

    def offer(self, route: RawRoute, fastest_s: float) -> None:
        if self.full:
            return
        if route.duration_s > MAX_DURATION_RATIO * fastest_s:
            self.rejected_slow += 1
            return
        if any(
            overlap_fraction(route.points, idx, OVERLAP_RADIUS_KM) > MAX_OVERLAP
            for idx in self._indexes
        ):
            return
        self.accepted.append(route)
        self._indexes.append(RouteIndex(route.points))


async def _via_routes(
    client: httpx.AsyncClient,
    provider: RoutingProvider,
    req: RouteRequest,
    fractions: tuple[float, ...],
) -> list[RawRoute]:
    vias = [perpendicular_via_point(req.origin, req.destination, f) for f in fractions]
    results = await asyncio.gather(
        *(provider.routes(client, req, via=v) for v in vias), return_exceptions=True
    )
    routes: list[RawRoute] = []
    for result in results:
        if isinstance(result, BaseException):
            # One unroutable via point (e.g. offshore) shouldn't sink the whole analysis.
            logger.info("via-point route failed: %r", result)
        else:
            routes.extend(result)
    return routes


async def _options_from(
    client: httpx.AsyncClient, provider: RoutingProvider, req: RouteRequest
) -> RouteOptions:
    base = await provider.routes(client, req)
    selector = _Selector()
    fastest = min(r.duration_s for r in base)
    for route in base:
        selector.offer(route, fastest)

    for fractions in VIA_OFFSET_ROUNDS:
        if selector.full:
            break
        for route in await _via_routes(client, provider, req, fractions):
            selector.offer(route, fastest)

    options = RouteOptions(selector.accepted, provider.name, provider.is_truck_profile)
    if not selector.full:
        options.warnings.append(
            f"Only {len(selector.accepted)} distinct route(s) found: other candidates overlapped "
            f"an existing route or were more than {MAX_DURATION_RATIO:g}x slower than the fastest."
        )
    if not provider.is_truck_profile:
        options.warnings.append(
            "Routes use a car profile (OSRM fallback); truck restrictions and load weight are not "
            "applied to routing. Set TOMTOM_API_KEY for truck routing."
        )
    return options


def _cache_key(req: RouteRequest, providers: list[RoutingProvider]) -> str:
    # TomTom's traffic-aware result depends on departure, so bucket it to 15 minutes.
    bucket = req.depart_at.replace(minute=req.depart_at.minute // 15 * 15, second=0, microsecond=0)
    raw = "|".join(
        [
            ",".join(p.name for p in providers),
            f"{req.origin[0]:.4f},{req.origin[1]:.4f}",
            f"{req.destination[0]:.4f},{req.destination[1]:.4f}",
            bucket.isoformat(),
            f"{req.load_lbs:.0f}",
        ]
    )
    return "routes:" + hashlib.sha1(raw.encode()).hexdigest()


async def get_route_options(
    client: httpx.AsyncClient, providers: list[RoutingProvider], req: RouteRequest
) -> RouteOptions:
    """Try providers in order; a failure falls through to the next one."""
    key = _cache_key(req, providers)
    cached = await cache.aget(key)
    if cached is not None:
        return cached

    errors: list[ProviderError] = []
    for provider in providers:
        try:
            options = await _options_from(client, provider, req)
        except ProviderError as exc:
            logger.warning("routing provider %s failed: %s", provider.name, exc)
            errors.append(exc)
            continue
        if errors:
            failed = ", ".join(e.provider for e in errors)
            options.warnings.insert(
                0, f"Primary routing provider ({failed}) failed; used {provider.name}."
            )
        await cache.aset(key, options, CACHE_TTL_S)
        return options

    no_route = any(e.code == "no_route" for e in errors)
    raise ProviderError(
        "routing",
        "no_route" if no_route else "unavailable",
        "No drivable route found between these locations."
        if no_route
        else "Routing providers are unavailable. Please try again shortly.",
    )
