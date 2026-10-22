import math

import pytest

from routing_app.geo import (
    RouteIndex,
    douglas_peucker,
    haversine_mi,
    overlap_fraction,
    perpendicular_via_point,
    simplify_to_max_points,
)

from .helpers import line

DALLAS, DENVER = (32.7767, -96.7970), (39.7392, -104.9903)


@pytest.mark.parametrize("fraction", [0.15, -0.15, 0.30, -0.30])
def test_via_point_offset_is_fraction_of_straight_line(fraction: float) -> None:
    mid = ((DALLAS[0] + DENVER[0]) / 2, (DALLAS[1] + DENVER[1]) / 2)
    via = perpendicular_via_point(DALLAS, DENVER, fraction)
    expected = abs(fraction) * haversine_mi(DALLAS, DENVER)
    assert haversine_mi(mid, via) == pytest.approx(expected, rel=0.02)
    # Perpendicular: equidistant from both ends, within the flat-projection error (~4% over
    # the 7° of latitude between Dallas and Denver).
    assert haversine_mi(DALLAS, via) == pytest.approx(haversine_mi(DENVER, via), rel=0.05)


def test_positive_offset_is_left_of_travel() -> None:
    # Travelling east, left is north.
    assert perpendicular_via_point((35, -100), (35, -95), 0.15)[0] > 35
    assert perpendicular_via_point((35, -100), (35, -95), -0.15)[0] < 35


def test_overlap_of_identical_route_is_total() -> None:
    route = line((35, -100), (35, -95))
    assert overlap_fraction(route, RouteIndex(route)) == 1.0


def test_parallel_route_beyond_one_km_does_not_overlap() -> None:
    route = line((35, -100), (35, -95))
    shifted = line((35.03, -100), (35.03, -95))  # ~3.3 km north.
    assert overlap_fraction(shifted, RouteIndex(route)) == 0.0


def test_partial_overlap() -> None:
    route = line((35, -100), (35, -95), n=100)
    half_shared = line((35, -100), (35, -97.5), 50) + line((35, -97.5), (36, -95), 50)[1:]
    assert 0.4 < overlap_fraction(half_shared, RouteIndex(route)) < 0.6


def test_douglas_peucker_drops_collinear_points_and_keeps_ends() -> None:
    assert douglas_peucker(line((35, -100), (35, -95), 100), 0.01) == [(35, -100), (35, -95)]


def test_douglas_peucker_keeps_corners() -> None:
    corner = line((35, -100), (36, -100), 20) + line((36, -100), (36, -99), 20)[1:]
    assert douglas_peucker(corner, 0.01) == [(35, -100), (36, -100), (36, -99)]


def test_simplify_respects_max_points() -> None:
    # A winding road: 5,000 vertices that cannot all survive a 300-point budget.
    road = [(35 + 0.05 * math.sin(i / 40), -100 + i * 0.001) for i in range(5000)]
    simplified = simplify_to_max_points(road, 300)
    assert len(simplified) <= 300
    assert simplified[0] == road[0] and simplified[-1] == road[-1]
