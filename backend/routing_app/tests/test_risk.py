import pytest

from routing_app.risk import (
    RiskLevel,
    apply_load_rules,
    classify_conditions,
    classify_rain,
    classify_snow,
    classify_wind,
)

L, M, H, S, N = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


@pytest.mark.parametrize(
    ("wind", "expected"),
    [
        (0, L), (24.99, L), (25, M), (34.99, M), (35, H), (44.99, H),
        (45, S), (54.99, S), (55, N), (80, N),
    ],
)  # fmt: skip
def test_wind_bands(wind: float, expected: RiskLevel) -> None:
    assert classify_wind(wind) == expected


@pytest.mark.parametrize(
    ("rain", "expected"),
    [
        (0, L), (0.0999, L), (0.10, M), (0.2499, M), (0.25, H), (0.4999, H),
        (0.50, S), (1.00, S), (1.0001, N), (2.5, N),
    ],
)  # fmt: skip
def test_rain_bands(rain: float, expected: RiskLevel) -> None:
    assert classify_rain(rain) == expected


@pytest.mark.parametrize(
    ("snow", "expected"),
    [
        (0, L), (0.4999, L), (0.5, M), (0.9999, M), (1.0, H), (1.9999, H),
        (2.0, S), (3.0, S), (3.0001, N), (6, N),
    ],
)  # fmt: skip
def test_snow_bands(snow: float, expected: RiskLevel) -> None:
    assert classify_snow(snow) == expected


def test_float_summation_noise_does_not_drop_a_band() -> None:
    # rain + showers can sum to 0.30000000000000004 or 0.09999999999999999.
    assert classify_rain(0.07 + 0.03) == M
    assert classify_rain(0.1 + 0.2) == H


def test_negative_inputs_are_treated_as_zero() -> None:
    assert classify_conditions(-1, -0.01, -0.5, 10_000).level == L


# --- Load rules ------------------------------------------------------------------------


@pytest.mark.parametrize("load", [1, 30_000, 80_000])
def test_wind_55_is_no_travel_for_any_load(load: float) -> None:
    assert classify_conditions(55, 0, 0, load).level == N


@pytest.mark.parametrize(
    ("wind", "load", "expected"),
    [
        (45, 30_000, S), (45, 30_001, N), (54.99, 30_000, S), (54.99, 30_001, N),
        (35, 40_000, H), (35, 40_001, S), (44.99, 40_000, H), (44.99, 40_001, S),
        # Just below each rule's wind band: no escalation.
        (44.99, 30_001, H), (34.99, 40_001, M),
    ],
)  # fmt: skip
def test_load_rule_thresholds(wind: float, load: float, expected: RiskLevel) -> None:
    assert classify_conditions(wind, 0, 0, load).level == expected


def test_load_rule_reason_names_the_rule() -> None:
    result = classify_conditions(47, 0, 0, 36_000)
    assert result.level == N
    assert result.weather_level == S
    assert result.drivers == ("wind", "load")
    assert result.reason == "wind 47 mph + load 36,000 lb → No Travel (load rule)"


@pytest.mark.parametrize("level", list(RiskLevel))
@pytest.mark.parametrize(("wind", "load"), [(10, 80_000), (40, 45_000), (50, 35_000)])
def test_load_rules_never_lower_a_level(level: RiskLevel, wind: float, load: float) -> None:
    assert apply_load_rules(level, wind, load).level >= level


def test_load_rule_is_silent_when_weather_already_worse() -> None:
    # 38 mph + 45,000 lb would be Severe, but 1.2 in/hr rain is already No Travel.
    result = classify_conditions(38, 1.2, 0, 45_000)
    assert result.level == N
    assert result.drivers == ("rain",)


# --- Combination -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("wind", "rain", "snow", "expected", "drivers"),
    [
        (10, 0, 0, L, ()),
        (30, 0.3, 0, H, ("rain",)),
        (40, 0.3, 0.6, H, ("wind", "rain")),
        (10, 0.05, 2.5, S, ("snow",)),
        (50, 0.6, 2.2, S, ("wind", "rain", "snow")),
        (20, 0.0, 3.5, N, ("snow",)),
    ],
)
def test_level_is_max_of_factors(
    wind: float, rain: float, snow: float, expected: RiskLevel, drivers: tuple[str, ...]
) -> None:
    result = classify_conditions(wind, rain, snow, 10_000)
    assert result.level == expected
    assert result.drivers == drivers


def test_reason_lists_driving_factors() -> None:
    assert classify_conditions(40, 0.3, 0, 10_000).reason == "wind 40 mph, rain 0.30 in/hr → High"
    assert classify_conditions(5, 0, 0, 10_000).reason.endswith("→ Low")
