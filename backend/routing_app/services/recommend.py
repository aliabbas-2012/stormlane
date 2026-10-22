"""Route ranking. Pure.

Lexicographic order (spec order, plus No Travel first; see README "Assumptions"):
  1. fewest No Travel miles   2. fewest Severe miles   3. fewest High miles
  4. lowest average risk      5. shortest travel time
Miles are compared rounded to 1 mi and average risk rounded to 0.05, so sampling noise
(e.g. 0.3 mi of Severe) cannot outrank a real difference further down the list.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .summary import RouteSummary

AVG_RISK_STEP = 0.05


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    route_id: str
    name: str  # "Route A"
    summary: RouteSummary


@dataclass(frozen=True, slots=True)
class Recommendation:
    ranked_ids: list[str]
    recommended_id: str
    reason: str
    no_safe_route: bool  # Every route crosses No Travel; the UI suggests delaying departure.


def _round_half_up(x: float) -> int:
    # round() is banker's rounding; a tolerance bucket must not depend on parity.
    return math.floor(x + 0.5)


def ranking_key(s: RouteSummary) -> tuple[int, int, int, int, float]:
    return (
        _round_half_up(s.no_travel_mi),
        _round_half_up(s.severe_mi),
        _round_half_up(s.high_mi),
        _round_half_up(s.avg_risk / AVG_RISK_STEP),
        s.duration_s,
    )


def format_duration(seconds: float) -> str:
    minutes = _round_half_up(abs(seconds) / 60)
    hours, mins = divmod(minutes, 60)
    return f"{hours} h {mins:02d} min" if hours else f"{mins} min"


def _time_clause(best: RouteSummary, other: RouteSummary) -> str:
    delta = best.duration_s - other.duration_s
    if abs(delta) < 60:
        return "same travel time"
    return f"{format_duration(delta)} {'longer' if delta > 0 else 'shorter'}"


def _explain(best: RouteCandidate, other: RouteCandidate) -> str:
    b, o = best.summary, other.summary
    kb, ko = ranking_key(b), ranking_key(o)
    head = f"{best.name}:"

    if kb[0] != ko[0]:
        risk = f"{kb[0]} No Travel miles ({other.name} has {ko[0]})"
    elif kb[1] != ko[1]:
        risk = f"{kb[1]} severe miles ({other.name} has {ko[1]})"
    elif kb[2] != ko[2]:
        risk = f"similar severe miles, {kb[2]} high miles ({other.name} has {ko[2]})"
    elif kb[3] != ko[3]:
        risk = (
            f"similar severe/high miles, lower average risk "
            f"{b.avg_risk:.2f} ({other.name} {o.avg_risk:.2f})"
        )
    elif b.duration_s < o.duration_s - 60:
        return f"{head} same risk profile as {other.name}, {_time_clause(b, o)}"
    else:
        return f"{head} equivalent to {other.name} on risk and time"
    return f"{head} {risk}; {_time_clause(b, o)}"


def rank_routes(candidates: Sequence[RouteCandidate]) -> Recommendation:
    if not candidates:
        raise ValueError("no routes to rank")
    # sorted() is stable: a full tie keeps provider order (the provider's preferred route).
    ranked = sorted(candidates, key=lambda c: ranking_key(c.summary))
    best = ranked[0]
    no_safe_route = all(c.summary.no_travel_mi > 0 for c in candidates)

    if len(ranked) == 1:
        reason = f"{best.name}: only one distinct route was found"
    else:
        reason = _explain(best, ranked[1])
    return Recommendation(
        ranked_ids=[c.route_id for c in ranked],
        recommended_id=best.route_id,
        reason=reason,
        no_safe_route=no_safe_route,
    )
