import random
from datetime import UTC, datetime
from itertools import pairwise

import pytest

from routing_app.geo import (
    build_checkpoints,
    checkpoint_miles,
    cumulative_miles,
    cumulative_seconds_from_segments,
    decode_polyline,
    encode_polyline,
    forecast_hours_for_eta,
    haversine_mi,
    ownership_bounds,
    point_at_mile,
    proportional_cumulative_seconds,
)

DALLAS = (32.7767, -96.7970)
DENVER = (39.7392, -104.9903)


def _random_route(seed: int, n: int = 200) -> list[tuple[float, float]]:
    rng = random.Random(seed)
    lat, lon = 35.0, -100.0
    points = [(lat, lon)]
    for _ in range(n):
        lat += rng.uniform(-0.02, 0.06)
        lon += rng.uniform(-0.02, 0.06)
        points.append((lat, lon))
    return points


# --- Polyline & distance ---------------------------------------------------------------


def test_decode_reference_polyline() -> None:
    # Example from Google's encoded polyline algorithm documentation.
    assert decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@") == [
        (38.5, -120.2),
        (40.7, -120.95),
        (43.252, -126.453),
    ]


@pytest.mark.parametrize("precision", [5, 6])
def test_polyline_round_trip(precision: int) -> None:
    points = [(round(a, precision), round(b, precision)) for a, b in _random_route(1, 50)]
    assert decode_polyline(encode_polyline(points, precision), precision) == points


def test_haversine_known_distances() -> None:
    assert haversine_mi((0, 0), (0, 1)) == pytest.approx(69.09, abs=0.05)
    assert haversine_mi(DALLAS, DENVER) == pytest.approx(663, rel=0.01)
    assert haversine_mi(DALLAS, DALLAS) == 0


def test_cumulative_miles_is_monotonic_and_ends_at_total() -> None:
    points = _random_route(2)
    cum = cumulative_miles(points)
    assert len(cum) == len(points)
    assert cum[0] == 0
    assert all(b >= a for a, b in pairwise(cum))
    assert cum[-1] == pytest.approx(sum(haversine_mi(a, b) for a, b in pairwise(points)))


def test_point_at_mile_interpolates_and_clamps() -> None:
    points = [(0.0, 0.0), (0.0, 1.0), (0.0, 2.0)]
    cum = cumulative_miles(points)
    lat, lon = point_at_mile(points, cum, cum[1] / 2)
    assert (lat, lon) == pytest.approx((0.0, 0.5))
    assert point_at_mile(points, cum, -5) == points[0]
    assert point_at_mile(points, cum, cum[-1] + 5) == pytest.approx(points[-1])


# --- Checkpoint placement & ownership ----------------------------------------------------


@pytest.mark.parametrize(
    ("total", "interval", "expected"),
    [
        (60, 25, [0, 25, 50, 60]),
        (50, 25, [0, 25, 50]),  # Destination coincides with a regular checkpoint: no duplicate.
        (10, 25, [0, 10]),
        (100, 10, [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]),
        (0, 25, [0]),
    ],
)
def test_checkpoint_miles(total: float, interval: float, expected: list[float]) -> None:
    assert checkpoint_miles(total, interval) == pytest.approx(expected)


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_checkpoint_spacing_equals_interval(interval: float) -> None:
    miles = checkpoint_miles(437.3, interval)
    gaps = [b - a for a, b in pairwise(miles)]
    assert all(g == pytest.approx(interval) for g in gaps[:-1])
    assert 0 < gaps[-1] <= interval


def test_ownership_bounds_midpoints() -> None:
    assert ownership_bounds([0, 25, 50, 60]) == [(0, 12.5), (12.5, 37.5), (37.5, 55), (55, 60)]


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("interval", [10, 25, 50])
def test_owned_miles_sum_to_route_length(seed: int, interval: float) -> None:
    points = _random_route(seed)
    cum = cumulative_miles(points)
    secs = proportional_cumulative_seconds(cum, 36_000)
    cps = build_checkpoints(points, cum, secs, interval)
    assert sum(cp.owned_mi for cp in cps) == pytest.approx(cum[-1], abs=1e-9)
    # Contiguous, gap-free coverage.
    assert cps[0].owns_from_mi == 0
    assert cps[-1].owns_to_mi == cum[-1]
    assert all(a.owns_to_mi == b.owns_from_mi for a, b in pairwise(cps))


def test_checkpoints_start_at_origin_and_end_at_destination() -> None:
    points = _random_route(7)
    cum = cumulative_miles(points)
    cps = build_checkpoints(points, cum, proportional_cumulative_seconds(cum, 1000), 25)
    assert cps[0].position == points[0]
    assert cps[-1].position == pytest.approx(points[-1])
    assert cps[-1].mile == cum[-1]


def test_zero_length_route_has_one_checkpoint() -> None:
    cps = build_checkpoints([DALLAS], [0.0], [0.0], 25)
    assert len(cps) == 1
    assert cps[0].owned_mi == 0


# --- ETA -----------------------------------------------------------------------------------


def test_proportional_eta_is_monotonic_and_spans_total_time() -> None:
    points = _random_route(3)
    cum = cumulative_miles(points)
    cps = build_checkpoints(points, cum, proportional_cumulative_seconds(cum, 20_000), 10)
    etas = [cp.elapsed_s for cp in cps]
    assert etas[0] == 0
    assert etas[-1] == pytest.approx(20_000)
    assert all(b > a for a, b in pairwise(etas))


def test_segment_durations_drive_eta() -> None:
    # Two equal-length segments; the second is driven three times slower.
    points = [(0.0, 0.0), (0.0, 1.0), (0.0, 2.0)]
    cum = cumulative_miles(points)
    secs = cumulative_seconds_from_segments([1000.0, 3000.0])
    assert secs == [0, 1000, 4000]
    cps = build_checkpoints(points, cum, secs, cum[-1] / 4)
    assert [cp.elapsed_s for cp in cps] == pytest.approx([0, 500, 1000, 2500, 4000])


def test_forecast_hours_for_eta() -> None:
    eta = datetime(2026, 10, 23, 14, 37, tzinfo=UTC)
    instant, accumulated = forecast_hours_for_eta(eta)
    assert instant == datetime(2026, 10, 23, 14, tzinfo=UTC)
    assert accumulated == datetime(2026, 10, 23, 15, tzinfo=UTC)
    on_the_hour = datetime(2026, 10, 23, 14, tzinfo=UTC)
    assert forecast_hours_for_eta(on_the_hour) == (on_the_hour, accumulated)
