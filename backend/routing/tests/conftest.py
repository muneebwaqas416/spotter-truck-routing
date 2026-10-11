"""Shared fixtures: fake provider responses and a clean cache for every test."""

from datetime import UTC, datetime, timedelta

import flexpolyline
import httpx
import pytest
import respx
from django.core.cache import cache
from django.test import override_settings

HERE_KEY = "test-key"


@pytest.fixture(autouse=True)
def _isolated(settings):
    cache.clear()
    settings.HERE_API_KEY = HERE_KEY
    # Outer mock with no routes: any HTTP call a test didn't explicitly mock fails loudly.
    with (
        respx.mock(assert_all_called=False),
        override_settings(
            REST_FRAMEWORK={**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}
        ),
    ):
        yield
    cache.clear()


def hour_floor(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


def open_meteo_response(
    request: httpx.Request, wind: float = 10, snow_cm: float = 0
) -> httpx.Response:
    """One location per requested coordinate, 72 hourly values starting an hour ago."""
    lats = request.url.params["latitude"].split(",")
    start = int((hour_floor(datetime.now(UTC)) - timedelta(hours=1)).timestamp())
    hours = 72

    def location():
        return {
            "hourly_units": {
                "wind_speed_10m": "mp/h",
                "rain": "inch",
                "showers": "inch",
                "snowfall": "cm",
            },
            "hourly": {
                "time": [start + h * 3600 for h in range(hours)],
                "wind_speed_10m": [wind] * hours,
                "wind_gusts_10m": [wind * 1.3] * hours,
                "rain": [0.02] * hours,
                "showers": [0.0] * hours,
                "snowfall": [snow_cm] * hours,
            },
        }

    body = [location() for _ in lats]
    return httpx.Response(200, json=body if len(body) > 1 else body[0])


def here_route(points: list[tuple[float, float]], duration_s: float, length_m: float) -> dict:
    """A HERE route with one section; `points` are (lat, lng)."""
    return {
        "sections": [
            {
                "polyline": flexpolyline.encode(points),
                "summary": {"duration": duration_s, "length": length_m},
                "spans": [{"offset": 0, "duration": duration_s, "length": length_m}],
            }
        ]
    }


DENVER = (39.7392, -104.9903)
SLC = (40.7608, -111.891)


def three_routes() -> dict:
    return {
        "routes": [
            here_route([DENVER, (41.3, -105.6), SLC], 9 * 3600, 880_000),
            here_route([DENVER, (40.5, -106.8), SLC], 8.3 * 3600, 700_000),
            here_route([DENVER, (39.1, -108.5), SLC], 9 * 3600, 800_000),
        ]
    }
