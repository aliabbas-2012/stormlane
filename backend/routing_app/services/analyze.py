"""POST /api/analyze orchestration: routes -> checkpoints -> weather at ETA -> risk -> rank."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from django.core.cache import cache

from routing_app.geo import (
    Checkpoint,
    LatLon,
    build_checkpoints,
    cumulative_miles,
    forecast_hours_for_eta,
    simplify_to_max_points,
)
from routing_app.providers.http import make_client
from routing_app.providers.routing import configured_providers
from routing_app.providers.types import RawRoute, RouteRequest
from routing_app.providers.weather import Forecast, fetch_forecasts, horizon_end
from routing_app.risk import RiskResult, classify_conditions

from .errors import ServiceError
from .recommend import RouteCandidate, rank_routes
from .route_options import get_route_options
from .summary import OwnedLevel, RouteSummary, merge_segments, summarize_route

ROUTE_NAMES = ("A", "B", "C")
MAX_GEOMETRY_POINTS = 2000
ANALYSIS_TTL_S = 60 * 60  # The heatmap request reads the stored analysis by id.
DEPARTURE_GRACE = timedelta(minutes=15)
US_GROSS_LIMIT_LBS = 80_000


@dataclass(frozen=True, slots=True)
class AnalyzeParams:
    origin: LatLon
    destination: LatLon
    origin_label: str
    destination_label: str
    departure: datetime  # Timezone-aware (any offset); normalised to UTC here.
    load_lbs: float
    interval_miles: int


@dataclass(frozen=True, slots=True)
class _ScoredCheckpoint:
    checkpoint: Checkpoint
    eta: datetime
    forecast_hour: datetime
    wind_mph: float
    gust_mph: float
    rain_in_hr: float
    snow_in_hr: float
    risk: RiskResult


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def validate_departure(departure: datetime, now: datetime) -> datetime:
    departure = departure.astimezone(UTC)
    if departure < now - DEPARTURE_GRACE:
        raise ServiceError("departure_in_past", "Departure time is in the past.")
    if departure > horizon_end(now):
        raise ServiceError(
            "beyond_forecast_horizon",
            "Departure is beyond the 16-day weather forecast horizon.",
        )
    return departure


def _score(
    checkpoints: list[Checkpoint],
    forecasts: list[Forecast],
    departure: datetime,
    load_lbs: float,
) -> list[_ScoredCheckpoint]:
    scored = []
    for cp, forecast in zip(checkpoints, forecasts, strict=True):
        eta = departure + timedelta(seconds=cp.elapsed_s)
        instant_hour, accumulation_hour = forecast_hours_for_eta(eta)
        instant, accumulated = forecast.get(instant_hour), forecast.get(accumulation_hour)
        if instant is None or accumulated is None:
            raise ServiceError(
                "forecast_unavailable",
                f"No forecast available near mile {cp.mile:.0f} at {iso(eta)}.",
                http_status=422,
            )
        # Wind is instantaneous at the hour containing the ETA; precipitation (and gust, a
        # preceding-hour max) come from the bucket that covers that hour.
        risk = classify_conditions(
            instant.wind_mph, accumulated.rain_in, accumulated.snow_in, load_lbs
        )
        scored.append(
            _ScoredCheckpoint(
                checkpoint=cp,
                eta=eta,
                forecast_hour=instant_hour,
                wind_mph=instant.wind_mph,
                gust_mph=accumulated.gust_mph,
                rain_in_hr=accumulated.rain_in,
                snow_in_hr=accumulated.snow_in,
                risk=risk,
            )
        )
    return scored


def _route_payload(
    route_id: str,
    route: RawRoute,
    cum_miles: list[float],
    scored: list[_ScoredCheckpoint],
    summary: RouteSummary,
    departure: datetime,
) -> dict[str, Any]:
    # Simplification keeps original vertices, so each kept vertex maps back to its exact
    # mile and elapsed time on the full route.
    index_of = {p: i for i, p in reversed(list(enumerate(route.points)))}
    simplified = simplify_to_max_points(route.points, MAX_GEOMETRY_POINTS)
    kept = [index_of[p] for p in simplified]
    owned = [
        OwnedLevel(s.checkpoint.owns_from_mi, s.checkpoint.owns_to_mi, s.risk.level) for s in scored
    ]
    worst = scored[summary.worst_checkpoint_index]
    return {
        "id": route_id,
        "name": f"Route {route_id}",
        "provider": route.provider,
        "synthesized": route.synthesized,
        "timing_source": route.timing_source,
        "geometry": {
            "type": "LineString",
            "coordinates": [[round(lon, 5), round(lat, 5)] for lat, lon in simplified],
        },
        "geometry_miles": [round(cum_miles[i], 3) for i in kept],
        "geometry_elapsed_s": [round(route.cum_seconds[i]) for i in kept],
        "distance_mi": round(summary.distance_mi, 1),
        "duration_s": round(route.duration_s),
        "arrival_time": iso(departure + timedelta(seconds=route.duration_s)),
        "summary": {
            "no_travel_miles": round(summary.no_travel_mi, 1),
            "severe_miles": round(summary.severe_mi, 1),
            "high_miles": round(summary.high_mi, 1),
            "moderate_miles": round(summary.miles_by_level[1], 1),
            "low_miles": round(summary.miles_by_level[0], 1),
            "avg_risk": summary.avg_risk,
            "max_level": int(summary.max_level),
            "worst_checkpoint": {
                "index": summary.worst_checkpoint_index,
                "mile": round(worst.checkpoint.mile, 1),
                "level": int(worst.risk.level),
                "reason": worst.risk.reason,
            },
        },
        "checkpoints": [
            {
                "mile": round(s.checkpoint.mile, 1),
                "lat": round(s.checkpoint.position[0], 5),
                "lon": round(s.checkpoint.position[1], 5),
                "eta": iso(s.eta),
                "forecast_hour": iso(s.forecast_hour),
                "wind_mph": round(s.wind_mph, 1),
                "gust_mph": round(s.gust_mph, 1),
                "rain_in_hr": round(s.rain_in_hr, 3),
                "snow_in_hr": round(s.snow_in_hr, 3),
                "level": int(s.risk.level),
                "drivers": list(s.risk.drivers),
                "reason": s.risk.reason,
            }
            for s in scored
        ],
        "segments": [
            {
                "from_mile": round(seg.from_mi, 3),
                "to_mile": round(seg.to_mi, 3),
                "level": int(seg.level),
            }
            for seg in merge_segments(owned)
        ],
    }


async def analyze(params: AnalyzeParams, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    departure = validate_departure(params.departure, now)
    warnings: list[str] = []
    if params.load_lbs > US_GROSS_LIMIT_LBS:
        warnings.append(
            f"Load of {params.load_lbs:,.0f} lb exceeds the {US_GROSS_LIMIT_LBS:,} lb US gross "
            "weight limit for travel without an oversize/overweight permit."
        )

    request = RouteRequest(params.origin, params.destination, departure, params.load_lbs)
    async with make_client() as client:
        options = await get_route_options(client, configured_providers(), request)
        warnings.extend(options.warnings)

        per_route = []
        for route in options.routes:
            cum = cumulative_miles(route.points)
            per_route.append(
                (
                    route,
                    cum,
                    build_checkpoints(route.points, cum, route.cum_seconds, params.interval_miles),
                )
            )

        last_needed = departure + timedelta(seconds=max(r.duration_s for r in options.routes))
        if forecast_hours_for_eta(last_needed)[1] > horizon_end(now):
            raise ServiceError(
                "beyond_forecast_horizon",
                "The trip ends beyond the 16-day forecast horizon; choose an earlier departure.",
            )
        # One batched weather request for every checkpoint of every route.
        positions = [cp.position for _, _, cps in per_route for cp in cps]
        all_forecasts = await fetch_forecasts(
            client, positions, departure, forecast_hours_for_eta(last_needed)[1]
        )

    routes_out, candidates, offset = [], [], 0
    for route_id, (route, cum, checkpoints) in zip(ROUTE_NAMES, per_route, strict=False):
        forecasts = all_forecasts[offset : offset + len(checkpoints)]
        offset += len(checkpoints)
        scored = _score(checkpoints, forecasts, departure, params.load_lbs)
        summary = summarize_route(
            [
                OwnedLevel(s.checkpoint.owns_from_mi, s.checkpoint.owns_to_mi, s.risk.level)
                for s in scored
            ],
            route.duration_s,
        )
        routes_out.append(_route_payload(route_id, route, cum, scored, summary, departure))
        candidates.append(RouteCandidate(route_id, f"Route {route_id}", summary))

    recommendation = rank_routes(candidates)
    analysis_id = uuid.uuid4().hex
    await cache.aset(
        f"analysis:{analysis_id}",
        {
            "departure": departure,
            "load_lbs": params.load_lbs,
            "routes": [
                {"id": r["id"], "coordinates": r["geometry"]["coordinates"]} for r in routes_out
            ],
        },
        ANALYSIS_TTL_S,
    )
    return {
        "analysis_id": analysis_id,
        "origin": {"lat": params.origin[0], "lon": params.origin[1], "label": params.origin_label},
        "destination": {
            "lat": params.destination[0],
            "lon": params.destination[1],
            "label": params.destination_label,
        },
        "departure_time": iso(departure),
        "load_lbs": params.load_lbs,
        "interval_miles": params.interval_miles,
        "provider": options.provider,
        "truck_profile": options.is_truck_profile,
        "routes": routes_out,
        "ranking": recommendation.ranked_ids,
        "recommended_route_id": recommendation.recommended_id,
        "recommendation_reason": recommendation.reason,
        "no_safe_route": recommendation.no_safe_route,
        "warnings": warnings,
    }
