"""Open-Meteo hourly forecasts, batched, cached per location, normalized to mph and in/hr.

Each location's full hourly series is cached for WEATHER_TTL_S; lookups pick the hour nearest
the requested time, so a cached series never serves one hour's data for another hour.
"""

import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from django.conf import settings

from routing.cache import get_many_or_fetch
from routing.exceptions import ProviderError

from .domain import MISSING_WEATHER, LngLat, WeatherSample
from .http import get_json

PROVIDER = "weather"
WEATHER_TTL_S = 30 * 60  # under Open-Meteo's ~hourly refresh
GRID_DEG = 0.1  # ~11 km; nearby points share a forecast
BATCH_SIZE = 100  # locations per request
FORECAST_DAYS = 16
HOURLY_VARIABLES = "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall"
CM_PER_INCH = 2.54
MM_PER_INCH = 25.4


@dataclass(frozen=True)
class HourlyForecast:
    start_epoch: int  # first hour, UTC seconds
    wind_mph: list[float | None]
    gust_mph: list[float | None]
    rain_in_hr: list[float | None]  # rain + showers
    snow_in_hr: list[float | None]
    fetched_at: datetime

    def at(self, when: datetime) -> WeatherSample:
        hour_epoch = round(when.timestamp() / 3600) * 3600
        index = (hour_epoch - self.start_epoch) // 3600
        if not 0 <= index < len(self.wind_mph):
            return MISSING_WEATHER  # beyond the forecast horizon
        return WeatherSample(
            forecast_time=datetime.fromtimestamp(hour_epoch, UTC),
            wind_mph=self.wind_mph[index],
            gust_mph=self.gust_mph[index],
            rain_in_hr=self.rain_in_hr[index],
            snow_in_hr=self.snow_in_hr[index],
        )


def snap(position: LngLat) -> LngLat:
    lon, lat = position
    return (round(lon / GRID_DEG) * GRID_DEG, round(lat / GRID_DEG) * GRID_DEG)


def _key(position: LngLat) -> str:
    lon, lat = position
    return f"v1:wx:{lat:.1f}:{lon:.1f}"


def forecasts(positions: Iterable[LngLat]) -> dict[str, HourlyForecast]:
    """Forecasts for every position (keyed by cache key); one provider call per batch of misses."""
    by_key = {_key(snap(p)): snap(p) for p in positions}
    return get_many_or_fetch(by_key, WEATHER_TTL_S, lambda keys: _fetch([by_key[k] for k in keys]))


def sample_at(found: dict[str, HourlyForecast], position: LngLat, when: datetime) -> WeatherSample:
    forecast = found.get(_key(snap(position)))
    return forecast.at(when) if forecast else MISSING_WEATHER


def _fetch(positions: list[LngLat]) -> dict[str, HourlyForecast]:
    result = {}
    for start in range(0, len(positions), BATCH_SIZE):
        batch = positions[start : start + BATCH_SIZE]
        data = get_json(
            PROVIDER,
            settings.OPEN_METEO_URL,
            {
                "latitude": ",".join(f"{lat:.1f}" for _, lat in batch),
                "longitude": ",".join(f"{lon:.1f}" for lon, _ in batch),
                "hourly": HOURLY_VARIABLES,
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "GMT",
                "timeformat": "unixtime",
                "forecast_days": FORECAST_DAYS,
            },
        )
        locations = data if isinstance(data, list) else [data]  # one location → plain object
        if len(locations) != len(batch):
            raise ProviderError(PROVIDER, "unexpected number of locations")
        for position, location in zip(batch, locations, strict=True):
            result[_key(position)] = _parse(location)
    return result


def _parse(location: dict) -> HourlyForecast:
    try:
        hourly = location["hourly"]
        units = location["hourly_units"]
        if units["wind_speed_10m"] not in ("mp/h", "mph"):
            raise ProviderError(PROVIDER, f"unexpected wind unit {units['wind_speed_10m']}")
        rain = _to_inches(hourly["rain"], units["rain"])
        showers = _to_inches(hourly["showers"], units["showers"])
        return HourlyForecast(
            start_epoch=int(hourly["time"][0]),
            wind_mph=hourly["wind_speed_10m"],
            gust_mph=hourly["wind_gusts_10m"],
            rain_in_hr=[
                None if r is None or s is None else r + s
                for r, s in zip(rain, showers, strict=True)
            ],
            snow_in_hr=_to_inches(hourly["snowfall"], units["snowfall"]),
            fetched_at=datetime.fromtimestamp(time.time(), UTC),
        )
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ProviderError(PROVIDER, "malformed forecast") from exc


def _to_inches(values: list[float | None], unit: str) -> list[float | None]:
    """Normalize whatever unit the provider used, rather than trusting the request parameter."""
    factor = {"inch": 1.0, "in": 1.0, "cm": 1 / CM_PER_INCH, "mm": 1 / MM_PER_INCH}.get(unit)
    if factor is None:
        raise ProviderError(PROVIDER, f"unexpected precipitation unit {unit}")
    return [None if v is None else v * factor for v in values]
