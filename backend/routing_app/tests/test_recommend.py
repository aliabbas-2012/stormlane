import pytest

from routing_app.risk import RiskLevel
from routing_app.services.recommend import RouteCandidate, format_duration, rank_routes
from routing_app.services.summary import OwnedLevel, RouteSummary, merge_segments, summarize_route

L, M, H, S, N = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


def summary(
    *,
    no_travel: float = 0,
    severe: float = 0,
    high: float = 0,
    avg: float = 0.5,
    hours: float = 10,
) -> RouteSummary:
    return RouteSummary(
        distance_mi=600,
        duration_s=hours * 3600,
        miles_by_level=(600 - no_travel - severe - high, 0, high, severe, no_travel),
        avg_risk=avg,
        max_level=L,
        worst_checkpoint_index=0,
    )


def cand(route_id: str, s: RouteSummary) -> RouteCandidate:
    return RouteCandidate(route_id, f"Route {route_id}", s)


# --- Summary -------------------------------------------------------------------------------


def test_summarize_route_miles_average_and_worst() -> None:
    cps = [
        OwnedLevel(0, 12.5, L),
        OwnedLevel(12.5, 37.5, H),
        OwnedLevel(37.5, 55, S),
        OwnedLevel(55, 60, H),
    ]
    s = summarize_route(cps, 3600)
    assert s.distance_mi == 60
    assert s.miles_by_level == (12.5, 0, 30, 17.5, 0)
    assert s.avg_risk == round((2 * 30 + 3 * 17.5) / 60, 2)
    assert s.max_level == S
    assert s.worst_checkpoint_index == 2


def test_merge_segments_collapses_equal_neighbours() -> None:
    cps = [OwnedLevel(0, 5, L), OwnedLevel(5, 10, L), OwnedLevel(10, 15, H), OwnedLevel(15, 20, L)]
    assert merge_segments(cps) == [
        OwnedLevel(0, 10, L),
        OwnedLevel(10, 15, H),
        OwnedLevel(15, 20, L),
    ]


# --- Ranking: one test per tiebreak level ----------------------------------------------------


def test_no_travel_miles_rank_first_even_over_severe() -> None:
    a = cand("A", summary(no_travel=5, severe=0, hours=8))
    b = cand("B", summary(no_travel=0, severe=80, hours=12))
    rec = rank_routes([a, b])
    assert rec.recommended_id == "B"
    assert rec.reason.startswith("Route B: 0 No Travel miles (Route A has 5)")
    assert not rec.no_safe_route


def test_fewest_severe_miles_wins() -> None:
    a = cand("A", summary(severe=38, hours=10))
    b = cand("B", summary(severe=0, high=100, hours=10 + 22 / 60))
    rec = rank_routes([a, b])
    assert rec.ranked_ids == ["B", "A"]
    assert rec.reason == "Route B: 0 severe miles (Route A has 38); 22 min longer"


def test_high_miles_break_severe_tie() -> None:
    a = cand("A", summary(severe=10, high=40))
    b = cand("B", summary(severe=10, high=15, hours=11))
    rec = rank_routes([a, b])
    assert rec.recommended_id == "B"
    assert "15 high miles (Route A has 40)" in rec.reason


def test_average_risk_breaks_high_tie() -> None:
    a = cand("A", summary(high=20, avg=0.80))
    b = cand("B", summary(high=20, avg=0.40, hours=12))
    rec = rank_routes([a, b])
    assert rec.recommended_id == "B"
    assert "lower average risk 0.40 (Route A 0.80)" in rec.reason
    assert rec.reason.endswith("2 h 00 min longer")


def test_travel_time_breaks_full_risk_tie() -> None:
    a = cand("A", summary(hours=10))
    b = cand("B", summary(hours=9.5))
    rec = rank_routes([a, b])
    assert rec.recommended_id == "B"
    assert rec.reason == "Route B: same risk profile as Route A, 30 min shorter"


# --- Tolerances ------------------------------------------------------------------------------


def test_sub_mile_severe_difference_is_noise() -> None:
    # 0.3 vs 0.0 severe miles both round to 0, so the faster route wins on time.
    a = cand("A", summary(severe=0.3, hours=9))
    b = cand("B", summary(severe=0.0, hours=10))
    assert rank_routes([a, b]).recommended_id == "A"


def test_average_risk_within_tolerance_falls_through_to_time() -> None:
    a = cand("A", summary(avg=0.51, hours=9))
    b = cand("B", summary(avg=0.49, hours=10))
    assert rank_routes([a, b]).recommended_id == "A"


def test_full_tie_keeps_provider_order() -> None:
    a, b = cand("A", summary()), cand("B", summary())
    rec = rank_routes([a, b])
    assert rec.recommended_id == "A"
    assert rec.reason == "Route A: equivalent to Route B on risk and time"


# --- Edge cases ------------------------------------------------------------------------------


def test_every_route_no_travel_flags_no_safe_route_but_still_ranks() -> None:
    a = cand("A", summary(no_travel=40))
    b = cand("B", summary(no_travel=12))
    c = cand("C", summary(no_travel=90))
    rec = rank_routes([a, b, c])
    assert rec.no_safe_route
    assert rec.ranked_ids == ["B", "A", "C"]


def test_single_route() -> None:
    rec = rank_routes([cand("A", summary())])
    assert rec.recommended_id == "A"
    assert "only one distinct route" in rec.reason


def test_rank_requires_routes() -> None:
    with pytest.raises(ValueError):
        rank_routes([])


@pytest.mark.parametrize(
    ("seconds", "text"), [(59, "1 min"), (1320, "22 min"), (3900, "1 h 05 min"), (-600, "10 min")]
)
def test_format_duration(seconds: float, text: str) -> None:
    assert format_duration(seconds) == text
