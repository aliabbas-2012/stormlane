"""Weather -> risk classification. Pure functions, no I/O.

Boundary policy: lower bounds are inclusive, so a value on a shared endpoint belongs to the
higher band (wind 35 -> High). The No Travel bound follows the spec's operators exactly:
wind >= 55, rain > 1.00, snow > 3.0.
"""

from bisect import bisect_right
from dataclasses import dataclass

from .levels import RiskLevel
from .load_rules import apply_load_rules

# Inclusive lower bounds of Moderate, High, Severe, No Travel (mph).
WIND_BOUNDS_MPH = (25.0, 35.0, 45.0, 55.0)
# Inclusive lower bounds of Moderate, High, Severe; No Travel is strictly above the cap (in/hr).
RAIN_BOUNDS_IN_HR = (0.10, 0.25, 0.50)
RAIN_NO_TRAVEL_ABOVE = 1.00
SNOW_BOUNDS_IN_HR = (0.5, 1.0, 2.0)
SNOW_NO_TRAVEL_ABOVE = 3.0

# Inputs are rounded to this many decimals first. This removes float summation noise
# (rain + showers can come out as 0.09999999999999999) without blurring real edge values
# such as 1.0001.
_INPUT_DECIMALS = 4


def _clean(value: float) -> float:
    return round(max(value, 0.0), _INPUT_DECIMALS)


def classify_wind(wind_mph: float) -> RiskLevel:
    return RiskLevel(bisect_right(WIND_BOUNDS_MPH, _clean(wind_mph)))


def classify_rain(rain_in_hr: float) -> RiskLevel:
    rain = _clean(rain_in_hr)
    if rain > RAIN_NO_TRAVEL_ABOVE:
        return RiskLevel.NO_TRAVEL
    return RiskLevel(bisect_right(RAIN_BOUNDS_IN_HR, rain))


def classify_snow(snow_in_hr: float) -> RiskLevel:
    snow = _clean(snow_in_hr)
    if snow > SNOW_NO_TRAVEL_ABOVE:
        return RiskLevel.NO_TRAVEL
    return RiskLevel(bisect_right(SNOW_BOUNDS_IN_HR, snow))


@dataclass(frozen=True, slots=True)
class RiskResult:
    level: RiskLevel
    weather_level: RiskLevel  # Before load rules.
    drivers: tuple[str, ...]  # Factors that set the level: "wind", "rain", "snow", "load".
    reason: str  # Human-readable, e.g. "wind 47 mph + load 36,000 lb → No Travel (load rule)".


def classify_conditions(
    wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lbs: float
) -> RiskResult:
    """Checkpoint level = max(wind, rain, snow level), then load rules (which only raise it).

    `rain_in_hr` is rain + showers. `wind_mph` is sustained 10 m wind; gusts are display-only.
    """
    wind, rain, snow = _clean(wind_mph), _clean(rain_in_hr), _clean(snow_in_hr)
    factor_levels = {
        "wind": classify_wind(wind),
        "rain": classify_rain(rain),
        "snow": classify_snow(snow),
    }
    descriptions = {
        "wind": f"wind {wind:.0f} mph",
        "rain": f"rain {rain:.2f} in/hr",
        "snow": f"snow {snow:.2f} in/hr",
    }
    weather_level = max(factor_levels.values())
    outcome = apply_load_rules(weather_level, wind, load_lbs)

    if outcome.rule is not None:
        reason = (
            f"{descriptions['wind']} + load {load_lbs:,.0f} lb → {outcome.level.label} (load rule)"
        )
        return RiskResult(outcome.level, weather_level, ("wind", "load"), reason)

    if weather_level == RiskLevel.LOW:
        reason = f"{', '.join(descriptions.values())} → Low"
        return RiskResult(weather_level, weather_level, (), reason)

    drivers = tuple(name for name, lvl in factor_levels.items() if lvl == weather_level)
    reason = f"{', '.join(descriptions[d] for d in drivers)} → {weather_level.label}"
    return RiskResult(weather_level, weather_level, drivers, reason)
