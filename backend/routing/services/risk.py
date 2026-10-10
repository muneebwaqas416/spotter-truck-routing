"""Weather-risk classification for one checkpoint. Pure functions; units are mph and in/hr.

Boundary convention (CLAUDE.md §3): a threshold value belongs to the higher level, except at
an explicit ">" in the spec (rain > 1.00, snow > 3.0), where the value stays in the lower level.
"""

from enum import IntEnum

from .domain import WeatherSample


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


LOAD_NO_TRAVEL_LB = 30_000  # wind 45-54 mph and load above this → No Travel
LOAD_SEVERE_LB = 40_000  # wind 35-44 mph and load above this → Severe


def classify_wind(mph: float) -> RiskLevel:
    if mph >= 55:
        return RiskLevel.NO_TRAVEL
    if mph >= 45:
        return RiskLevel.SEVERE
    if mph >= 35:
        return RiskLevel.HIGH
    if mph >= 25:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def classify_rain(in_hr: float) -> RiskLevel:
    if in_hr > 1.00:
        return RiskLevel.NO_TRAVEL
    if in_hr >= 0.50:
        return RiskLevel.SEVERE
    if in_hr >= 0.25:
        return RiskLevel.HIGH
    if in_hr >= 0.10:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def classify_snow(in_hr: float) -> RiskLevel:
    if in_hr > 3.0:
        return RiskLevel.NO_TRAVEL
    if in_hr >= 2.0:
        return RiskLevel.SEVERE
    if in_hr >= 1.0:
        return RiskLevel.HIGH
    if in_hr >= 0.5:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def apply_load_rules(wind_level: RiskLevel, wind_mph: float, load_lb: int) -> RiskLevel:
    """Heavier loads are more exposed to wind. Never lowers the base level."""
    if 45 <= wind_mph < 55 and load_lb > LOAD_NO_TRAVEL_LB:
        return RiskLevel.NO_TRAVEL
    if 35 <= wind_mph < 45 and load_lb > LOAD_SEVERE_LB:
        return max(wind_level, RiskLevel.SEVERE)
    return wind_level


def assess(sample: WeatherSample, load_lb: int) -> tuple[RiskLevel | None, list[str]]:
    """Worst of wind (after load rules), rain and snow. Missing data → (None, reason), never Low."""
    if sample.wind_mph is None or sample.rain_in_hr is None or sample.snow_in_hr is None:
        return None, ["Forecast unavailable for this time"]

    base_wind = classify_wind(sample.wind_mph)
    wind = apply_load_rules(base_wind, sample.wind_mph, load_lb)
    rain = classify_rain(sample.rain_in_hr)
    snow = classify_snow(sample.snow_in_hr)

    reasons = []
    if wind > base_wind:
        limit = LOAD_NO_TRAVEL_LB if wind == RiskLevel.NO_TRAVEL else LOAD_SEVERE_LB
        reasons.append(f"Wind {sample.wind_mph:.0f} mph with load > {limit:,} lb")
    elif wind > RiskLevel.LOW:
        reasons.append(f"Wind {sample.wind_mph:.0f} mph")
    if rain > RiskLevel.LOW:
        reasons.append(f"Rain {sample.rain_in_hr:.2f} in/hr")
    if snow > RiskLevel.LOW:
        reasons.append(f"Snow {sample.snow_in_hr:.1f} in/hr")

    return max(wind, rain, snow), reasons
