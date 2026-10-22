"""Checkpoint placement and segment ownership along a route."""

from dataclasses import dataclass
from itertools import pairwise

from .interpolate import point_at_mile, value_at_mile
from .types import LatLon

# A final regular checkpoint closer than this to the destination is merged into it,
# so the destination is never a duplicate point.
_DUPLICATE_EPS_MI = 1e-6


@dataclass(frozen=True, slots=True)
class Checkpoint:
    index: int
    mile: float
    position: LatLon
    elapsed_s: float
    owns_from_mi: float
    owns_to_mi: float

    @property
    def owned_mi(self) -> float:
        return self.owns_to_mi - self.owns_from_mi


def checkpoint_miles(total_mi: float, interval_mi: float) -> list[float]:
    """Mile 0, I, 2I, ... strictly before the end, plus the destination."""
    if interval_mi <= 0:
        raise ValueError("interval_mi must be positive")
    if total_mi <= 0:
        return [0.0]
    count = int(total_mi // interval_mi)
    miles = [k * interval_mi for k in range(count + 1)]
    if total_mi - miles[-1] > _DUPLICATE_EPS_MI:
        miles.append(total_mi)
    else:
        miles[-1] = total_mi
    return miles


def ownership_bounds(miles: list[float]) -> list[tuple[float, float]]:
    """Each checkpoint owns from the midpoint to its predecessor up to the midpoint to its
    successor, clipped to the route. Neighbours share their boundaries, so the owned lengths
    telescope to exactly the route length."""
    boundaries = [miles[0], *((a + b) / 2 for a, b in pairwise(miles)), miles[-1]]
    return list(pairwise(boundaries))


def build_checkpoints(
    points: list[LatLon],
    cum_miles: list[float],
    cum_seconds: list[float],
    interval_mi: float,
) -> list[Checkpoint]:
    if not (len(points) == len(cum_miles) == len(cum_seconds)) or not points:
        raise ValueError("points, cum_miles and cum_seconds must be equal-length and non-empty")
    miles = checkpoint_miles(cum_miles[-1], interval_mi)
    if len(miles) == 1:  # Zero-length route: one checkpoint owning nothing.
        return [Checkpoint(0, 0.0, points[0], 0.0, 0.0, 0.0)]
    return [
        Checkpoint(
            index=i,
            mile=mile,
            position=point_at_mile(points, cum_miles, mile),
            elapsed_s=value_at_mile(cum_miles, cum_seconds, mile),
            owns_from_mi=lo,
            owns_to_mi=hi,
        )
        for i, (mile, (lo, hi)) in enumerate(zip(miles, ownership_bounds(miles), strict=True))
    ]
