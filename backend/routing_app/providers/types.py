from dataclasses import dataclass
from datetime import datetime

from routing_app.geo import LatLon


@dataclass(frozen=True, slots=True)
class RouteRequest:
    origin: LatLon
    destination: LatLon
    depart_at: datetime  # Timezone-aware, UTC.
    load_lbs: float


@dataclass(frozen=True, slots=True)
class RawRoute:
    """A provider route normalised to what the pipeline needs."""

    points: list[LatLon]
    cum_seconds: list[float]  # Elapsed time at each vertex; same length as points.
    distance_m: float
    duration_s: float
    provider: str
    timing_source: str  # "segments" (provider per-stretch timing) or "proportional".
    synthesized: bool = (
        False  # Built through a via waypoint rather than returned as an alternative.
    )
