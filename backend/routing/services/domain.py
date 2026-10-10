"""Plain data types shared across services. No Django, no HTTP."""

from dataclasses import dataclass, field
from datetime import datetime

# (longitude, latitude), matching GeoJSON and the frontend.
LngLat = tuple[float, float]


@dataclass(frozen=True)
class Place:
    label: str
    position: LngLat


@dataclass(frozen=True)
class RoutePath:
    """A route as the rest of the system sees it, independent of the routing provider."""

    coordinates: list[LngLat]
    distance_mi: float
    duration_s: float
    # Elapsed seconds at each coordinate (same length as `coordinates`), from provider timings.
    elapsed_s: list[float]
    is_fallback_alternative: bool = False


@dataclass(frozen=True)
class WeatherSample:
    """Forecast at one place and hour. None means the provider had no value."""

    forecast_time: datetime | None
    wind_mph: float | None
    gust_mph: float | None
    rain_in_hr: float | None
    snow_in_hr: float | None


MISSING_WEATHER = WeatherSample(None, None, None, None, None)


@dataclass(frozen=True)
class Checkpoint:
    index: int
    position: LngLat
    mile: float
    eta: datetime
    weather: WeatherSample = MISSING_WEATHER
    level: int | None = None  # RiskLevel value; None = unknown
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Suggestion:
    id: str
    label: str
    position: LngLat
