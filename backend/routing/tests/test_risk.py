import pytest

from routing.services.domain import WeatherSample
from routing.services.risk import (
    RiskLevel,
    apply_load_rules,
    assess,
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
    ("mph", "level"),
    [(0, L), (24.9, L), (25, M), (34.9, M), (35, H), (44.9, H), (45, S), (54.9, S), (55, N)],
)
def test_wind_thresholds(mph, level):
    assert classify_wind(mph) == level


@pytest.mark.parametrize(
    ("in_hr", "level"),
    [
        (0, L),
        (0.09, L),
        (0.10, M),
        (0.24, M),
        (0.25, H),
        (0.49, H),
        (0.50, S),
        (1.00, S),  # spec says "> 1.00" for No Travel, so 1.00 itself is Severe
        (1.01, N),
    ],
)
def test_rain_thresholds(in_hr, level):
    assert classify_rain(in_hr) == level


@pytest.mark.parametrize(
    ("in_hr", "level"),
    [(0, L), (0.49, L), (0.5, M), (0.99, M), (1.0, H), (1.99, H), (2.0, S), (3.0, S), (3.01, N)],
)
def test_snow_thresholds(in_hr, level):
    assert classify_snow(in_hr) == level


@pytest.mark.parametrize(
    ("mph", "load", "expected"),
    [
        (45, 30_000, S),  # exactly 30,000 does not trigger "> 30,000"
        (45, 30_001, N),
        (54.9, 45_000, N),
        (35, 40_000, H),  # exactly 40,000 does not trigger "> 40,000"
        (35, 40_001, S),
        (44.9, 80_000, S),
        (30, 80_000, M),  # load rules only apply in their wind bands
    ],
)
def test_load_rules(mph, load, expected):
    assert apply_load_rules(classify_wind(mph), mph, load) == expected


@pytest.mark.parametrize("load", [1, 20_000, 80_000])
def test_wind_at_or_above_55_is_no_travel_for_any_load(load):
    level, _ = assess(WeatherSample(None, 55, 60, 0, 0), load)
    assert level == N


def test_load_rules_never_downgrade():
    assert apply_load_rules(N, 60, 50_000) == N


def test_worst_condition_wins_with_reasons():
    level, reasons = assess(WeatherSample(None, 38, 48, 0.3, 0.0), 42_000)
    assert level == S
    assert reasons == ["Wind 38 mph with load > 40,000 lb", "Rain 0.30 in/hr"]


@pytest.mark.parametrize("field", ["wind_mph", "rain_in_hr", "snow_in_hr"])
def test_missing_weather_is_unknown_never_low(field):
    values = {"wind_mph": 5.0, "rain_in_hr": 0.0, "snow_in_hr": 0.0}
    values[field] = None
    level, reasons = assess(WeatherSample(None, gust_mph=None, **values), 10_000)
    assert level is None
    assert reasons == ["Forecast unavailable for this time"]
