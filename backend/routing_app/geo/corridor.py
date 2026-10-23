"""Heatmap sampling grid over the trip corridor.

Rather than offset points that then need deduplicating, we take every cell of a global
lat/lon lattice whose centre lies within CORRIDOR_HALF_WIDTH_MI of any route. That gives:
- uniform spacing, so the heatmap's kernel density reflects weather rather than how many
  sample points happened to overlap (routes converging near the ends, etc.);
- stable coordinates across trips, so forecast cache entries are reused;
- built-in dedupe, since a cell can only be selected once.
The lattice coarsens until the point count fits the budget (Open-Meteo counts each location).
"""

import math

from .distance import haversine_mi
from .projection import MI_PER_DEG_LAT
from .similarity import resample
from .types import LatLon

CORRIDOR_HALF_WIDTH_MI = 30.0
INITIAL_CELL_DEG = 0.2
MAX_POINTS = 250
_COARSEN_FACTOR = 1.25
_SAMPLE_STEP_MI = 5.0


def _cells_near(p: LatLon, cell_deg: float, radius_mi: float) -> list[tuple[int, int]]:
    lat_span = radius_mi / MI_PER_DEG_LAT
    lon_span = radius_mi / (MI_PER_DEG_LAT * max(math.cos(math.radians(p[0])), 0.1))
    i0, i1 = math.floor((p[0] - lat_span) / cell_deg), math.floor((p[0] + lat_span) / cell_deg)
    j0, j1 = math.floor((p[1] - lon_span) / cell_deg), math.floor((p[1] + lon_span) / cell_deg)
    return [
        (i, j)
        for i in range(i0, i1 + 1)
        for j in range(j0, j1 + 1)
        if haversine_mi(p, ((i + 0.5) * cell_deg, (j + 0.5) * cell_deg)) <= radius_mi
    ]


def corridor_cells(routes: list[list[LatLon]], cell_deg: float) -> list[LatLon]:
    """Centres of lattice cells within the corridor, in a deterministic order."""
    cells: set[tuple[int, int]] = set()
    for route in routes:
        for p in resample(route, _SAMPLE_STEP_MI):
            cells.update(_cells_near(p, cell_deg, CORRIDOR_HALF_WIDTH_MI))
    return [((i + 0.5) * cell_deg, (j + 0.5) * cell_deg) for i, j in sorted(cells)]


def corridor_grid(
    routes: list[list[LatLon]], max_points: int = MAX_POINTS
) -> tuple[list[LatLon], float]:
    """(points, cell size in degrees) with len(points) <= max_points."""
    cell = INITIAL_CELL_DEG
    while True:
        points = corridor_cells(routes, cell)
        if len(points) <= max_points:
            return points, cell
        cell *= _COARSEN_FACTOR
