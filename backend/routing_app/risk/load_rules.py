"""Load-weight escalation rules. They are applied after the weather classification and can
only raise a level, because a heavier truck is never safer in high wind."""

from dataclasses import dataclass

from .levels import RiskLevel

NO_TRAVEL_WIND_MPH = 55.0
HEAVY_LOAD_LBS = 30_000  # 45 <= wind < 55 with load above this -> No Travel
HEAVIER_LOAD_LBS = 40_000  # 35 <= wind < 45 with load above this -> Severe


@dataclass(frozen=True, slots=True)
class LoadRuleOutcome:
    level: RiskLevel
    rule: str | None  # Description of the rule that raised the level, if any.


def apply_load_rules(level: RiskLevel, wind_mph: float, load_lbs: float) -> LoadRuleOutcome:
    if wind_mph >= NO_TRAVEL_WIND_MPH:
        # Already No Travel from the wind table; asserted here so the rule stands on its own.
        target, rule = RiskLevel.NO_TRAVEL, None
    elif wind_mph >= 45 and load_lbs > HEAVY_LOAD_LBS:
        target, rule = RiskLevel.NO_TRAVEL, f"load > {HEAVY_LOAD_LBS:,} lb in 45-55 mph wind"
    elif wind_mph >= 35 and load_lbs > HEAVIER_LOAD_LBS:
        target, rule = RiskLevel.SEVERE, f"load > {HEAVIER_LOAD_LBS:,} lb in 35-45 mph wind"
    else:
        return LoadRuleOutcome(level, None)

    if target > level:
        return LoadRuleOutcome(target, rule)
    return LoadRuleOutcome(level, None)
