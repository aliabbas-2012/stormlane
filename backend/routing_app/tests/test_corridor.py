import pytest

from routing_app.geo import haversine_mi
from routing_app.geo.corridor import CORRIDOR_HALF_WIDTH_MI, corridor_cells, corridor_grid

from .helpers import line

EAST_WEST = line((35.0, -100.0), (35.0, -96.0), 80)


def _distance_to_route(p: tuple[float, float], route: list[tuple[float, float]]) -> float:
    return min(haversine_mi(p, q) for q in route)


def test_cells_cover_the_corridor_and_nothing_beyond_it() -> None:
    cells = corridor_cells([EAST_WEST], 0.2)
    dense = line((35.0, -100.0), (35.0, -96.0), 800)
    assert all(_distance_to_route(c, dense) <= CORRIDOR_HALF_WIDTH_MI + 1 for c in cells)
    # Both sides are covered laterally: at 0.2° the outermost centres sit 0.3° (~21 mi) out;
    # the next ring (0.5°, ~35 mi) is beyond the half-width.
    lats = sorted({round(c[0], 2) for c in cells})
    assert lats[0] <= 34.7 and lats[-1] >= 35.3


def test_cells_sit_on_a_global_lattice() -> None:
    for lat, lon in corridor_cells([EAST_WEST], 0.2):
        assert (lat / 0.2 - 0.5) == pytest.approx(round(lat / 0.2 - 0.5), abs=1e-9)
        assert (lon / 0.2 - 0.5) == pytest.approx(round(lon / 0.2 - 0.5), abs=1e-9)


def test_overlapping_routes_do_not_duplicate_points() -> None:
    single = corridor_cells([EAST_WEST], 0.2)
    assert corridor_cells([EAST_WEST, EAST_WEST], 0.2) == single


def test_grid_coarsens_to_fit_the_budget() -> None:
    long_route = line((34.0, -118.0), (40.7, -74.0), 400)  # ~LA to NYC
    points, cell = corridor_grid([long_route], max_points=250)
    assert len(points) <= 250
    assert cell > 0.2
    short_points, short_cell = corridor_grid([EAST_WEST], max_points=1000)
    assert short_cell == 0.2
    assert len(short_points) > 0
