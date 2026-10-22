"""Per-route risk metrics derived from checkpoint levels and their owned miles. Pure."""

from collections.abc import Sequence
from dataclasses import dataclass

from routing_app.risk import RiskLevel


@dataclass(frozen=True, slots=True)
class OwnedLevel:
    """A stretch of route [from_mi, to_mi) and the risk level that governs it."""

    from_mi: float
    to_mi: float
    level: RiskLevel

    @property
    def length_mi(self) -> float:
        return self.to_mi - self.from_mi


@dataclass(frozen=True, slots=True)
class RouteSummary:
    distance_mi: float
    duration_s: float
    miles_by_level: tuple[float, float, float, float, float]  # Indexed by RiskLevel.
    avg_risk: float  # Distance-weighted, 0-4, 2 decimals.
    max_level: RiskLevel
    worst_checkpoint_index: int  # First checkpoint at max_level.

    def miles_at(self, level: RiskLevel) -> float:
        return self.miles_by_level[level]

    @property
    def no_travel_mi(self) -> float:
        return self.miles_by_level[RiskLevel.NO_TRAVEL]

    @property
    def severe_mi(self) -> float:
        return self.miles_by_level[RiskLevel.SEVERE]

    @property
    def high_mi(self) -> float:
        return self.miles_by_level[RiskLevel.HIGH]


def summarize_route(checkpoints: Sequence[OwnedLevel], duration_s: float) -> RouteSummary:
    if not checkpoints:
        raise ValueError("a route needs at least one checkpoint")
    miles = [0.0] * len(RiskLevel)
    for cp in checkpoints:
        miles[cp.level] += cp.length_mi
    distance = sum(miles)
    weighted = sum(level * mi for level, mi in enumerate(miles))
    max_level = max(cp.level for cp in checkpoints)
    worst = next(i for i, cp in enumerate(checkpoints) if cp.level == max_level)
    return RouteSummary(
        distance_mi=distance,
        duration_s=duration_s,
        miles_by_level=(miles[0], miles[1], miles[2], miles[3], miles[4]),
        avg_risk=round(weighted / distance, 2) if distance > 0 else float(max_level),
        max_level=max_level,
        worst_checkpoint_index=worst,
    )


def merge_segments(checkpoints: Sequence[OwnedLevel]) -> list[OwnedLevel]:
    """Collapse adjacent stretches with the same level, so the map draws fewer features."""
    merged: list[OwnedLevel] = []
    for cp in checkpoints:
        if cp.length_mi <= 0:
            continue
        if merged and merged[-1].level == cp.level and merged[-1].to_mi == cp.from_mi:
            merged[-1] = OwnedLevel(merged[-1].from_mi, cp.to_mi, cp.level)
        else:
            merged.append(cp)
    return merged
