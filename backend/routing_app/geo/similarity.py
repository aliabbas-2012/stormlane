"""Geometric overlap between routes, used to discard near-duplicate alternatives."""

import math
from collections import defaultdict

from .distance import cumulative_miles, haversine_mi
from .interpolate import point_at_mile
from .types import LatLon

KM_PER_MI = 1.609344
_CELL_DEG = 0.02  # ~2.2 km in latitude; with a 3x3 neighbourhood this covers a 1 km radius.


def resample(points: list[LatLon], step_mi: float) -> list[LatLon]:
    cum = cumulative_miles(points)
    total = cum[-1]
    count = max(int(total / step_mi), 1)
    return [point_at_mile(points, cum, total * k / count) for k in range(count + 1)]


class RouteIndex:
    """Spatial hash over a densely resampled route for fast 'is this point near it' checks."""

    def __init__(self, points: list[LatLon], step_mi: float = 0.25):
        self._cells: dict[tuple[int, int], list[LatLon]] = defaultdict(list)
        for p in resample(points, step_mi):
            self._cells[self._cell(p)].append(p)

    @staticmethod
    def _cell(p: LatLon) -> tuple[int, int]:
        return math.floor(p[0] / _CELL_DEG), math.floor(p[1] / _CELL_DEG)

    def is_near(self, p: LatLon, radius_mi: float) -> bool:
        ci, cj = self._cell(p)
        return any(
            haversine_mi(p, q) <= radius_mi
            for di in (-1, 0, 1)
            for dj in (-1, 0, 1)
            for q in self._cells.get((ci + di, cj + dj), ())
        )


def overlap_fraction(
    candidate: list[LatLon], existing: RouteIndex, radius_km: float = 1.0, samples: int = 200
) -> float:
    """Share of evenly spaced candidate points lying within `radius_km` of the existing route.

    The existing route is resampled every 0.25 mi, so 'distance to the polyline' is
    approximated to within ~0.2 km, which is well inside the 1 km tolerance."""
    cum = cumulative_miles(candidate)
    if cum[-1] <= 0:
        return 1.0
    radius_mi = radius_km / KM_PER_MI
    sampled = [point_at_mile(candidate, cum, cum[-1] * k / samples) for k in range(samples + 1)]
    return sum(existing.is_near(p, radius_mi) for p in sampled) / len(sampled)
