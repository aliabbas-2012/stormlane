"""Routing providers behind one interface. TomTom (truck profile) is primary when a key is
configured; the public OSRM server (car profile) is the fallback."""

from typing import Any, Protocol

import httpx
from django.conf import settings

from routing_app.geo import (
    LatLon,
    cumulative_miles,
    cumulative_seconds_from_segments,
    decode_polyline,
    proportional_cumulative_seconds,
    value_at_mile,
)

from .http import ProviderError, get_json
from .types import RawRoute, RouteRequest

LB_TO_KG = 0.45359237
MAX_ALTERNATIVES = 2  # Primary + 2 alternatives = the 3 routes we want.


class RoutingProvider(Protocol):
    name: str
    is_truck_profile: bool

    async def routes(
        self, client: httpx.AsyncClient, req: RouteRequest, via: LatLon | None = None
    ) -> list[RawRoute]:
        """Routes for `req`. With `via`, a single route forced through that point;
        without it, the best route plus up to MAX_ALTERNATIVES alternatives."""
        ...


# --- OSRM ----------------------------------------------------------------------------------


class OsrmProvider:
    name = "osrm"
    is_truck_profile = False

    def __init__(self, base_url: str = "https://router.project-osrm.org"):
        self.base_url = base_url.rstrip("/")

    async def routes(
        self, client: httpx.AsyncClient, req: RouteRequest, via: LatLon | None = None
    ) -> list[RawRoute]:
        stops = [req.origin, *([via] if via else []), req.destination]
        coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in stops)
        params = {
            # OSRM only computes alternatives between exactly two coordinates.
            "alternatives": "false" if via else str(MAX_ALTERNATIVES),
            "overview": "full",
            "geometries": "polyline6",
            "annotations": "duration,distance",
            "steps": "false",
        }
        url = f"{self.base_url}/route/v1/driving/{coords}"
        data = await get_json(client, self.name, url, params)
        if data.get("code") != "Ok" or not data.get("routes"):
            raise ProviderError(self.name, "no_route", data.get("message") or "no route found")
        return [parse_osrm_route(r, synthesized=via is not None) for r in data["routes"]]


def parse_osrm_route(route: dict[str, Any], synthesized: bool = False) -> RawRoute:
    points = decode_polyline(route["geometry"], precision=6)
    durations = [d for leg in route["legs"] for d in leg.get("annotation", {}).get("duration", [])]
    total_s = float(route["duration"])
    if len(durations) == len(points) - 1 and sum(durations) > 0:
        # Per-segment durations are rounded, so they sum slightly short of the route total;
        # rescale so the final ETA matches the duration we display.
        scale = total_s / sum(durations)
        cum_seconds = cumulative_seconds_from_segments([d * scale for d in durations])
        timing = "segments"
    else:
        cum_seconds = proportional_cumulative_seconds(cumulative_miles(points), total_s)
        timing = "proportional"
    return RawRoute(
        points=points,
        cum_seconds=cum_seconds,
        distance_m=float(route["distance"]),
        duration_s=total_s,
        provider="osrm",
        timing_source=timing,
        synthesized=synthesized,
    )


# --- TomTom --------------------------------------------------------------------------------


class TomTomProvider:
    name = "tomtom"
    is_truck_profile = True

    def __init__(self, api_key: str, base_url: str = "https://api.tomtom.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def routes(
        self, client: httpx.AsyncClient, req: RouteRequest, via: LatLon | None = None
    ) -> list[RawRoute]:
        stops = [req.origin, *([via] if via else []), req.destination]
        locations = ":".join(f"{lat:.6f},{lon:.6f}" for lat, lon in stops)
        params: list[tuple[str, str | int]] = [
            ("key", self.api_key),
            ("travelMode", "truck"),
            ("vehicleCommercial", "true"),
            ("vehicleWeight", round(req.load_lbs * LB_TO_KG)),
            ("maxAlternatives", 0 if via else MAX_ALTERNATIVES),
            ("departAt", req.depart_at.isoformat(timespec="seconds")),
            ("routeRepresentation", "polyline"),
            # Cumulative travel time at a subset of points -> traffic-aware checkpoint ETAs.
            ("extendedRouteRepresentation", "travelTime"),
            ("traffic", "true"),
        ]
        url = f"{self.base_url}/routing/1/calculateRoute/{locations}/json"
        data = await get_json(client, self.name, url, params)
        if not data.get("routes"):
            raise ProviderError(self.name, "no_route", "no route found")
        return [parse_tomtom_route(r, synthesized=via is not None) for r in data["routes"]]


def parse_tomtom_route(route: dict[str, Any], synthesized: bool = False) -> RawRoute:
    # Points are concatenated across legs without removing the shared leg boundary, so that
    # indices stay aligned with progress[].pointIndex.
    points = [(p["latitude"], p["longitude"]) for leg in route["legs"] for p in leg["points"]]
    if len(points) < 2:
        raise ProviderError("tomtom", "bad_response", "route has no geometry")
    summary = route["summary"]
    total_s = float(summary["travelTimeInSeconds"])
    cum_miles = cumulative_miles(points)
    progress = [
        p for p in route.get("progress", []) if "travelTimeInSeconds" in p and "pointIndex" in p
    ]
    if len(progress) >= 2 and progress[-1]["pointIndex"] == len(points) - 1:
        # progress[] is cumulative but sparse; TomTom's guidance is to interpolate by distance.
        known_miles = [cum_miles[p["pointIndex"]] for p in progress]
        known_secs = [float(p["travelTimeInSeconds"]) for p in progress]
        cum_seconds = [value_at_mile(known_miles, known_secs, m) for m in cum_miles]
        timing = "segments"
    else:
        cum_seconds = proportional_cumulative_seconds(cum_miles, total_s)
        timing = "proportional"
    return RawRoute(
        points=points,
        cum_seconds=cum_seconds,
        distance_m=float(summary["lengthInMeters"]),
        duration_s=total_s,
        provider="tomtom",
        timing_source=timing,
        synthesized=synthesized,
    )


def configured_providers() -> list[RoutingProvider]:
    """Providers in preference order."""
    providers: list[RoutingProvider] = []
    if settings.TOMTOM_API_KEY:
        providers.append(TomTomProvider(settings.TOMTOM_API_KEY))
    providers.append(OsrmProvider())
    return providers
