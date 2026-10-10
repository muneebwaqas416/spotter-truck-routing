from datetime import UTC, datetime

import httpx
import pytest
import respx
from django.conf import settings

from routing.exceptions import ProviderError, ProviderTimeout
from routing.services import weather
from routing.tests.conftest import hour_floor, open_meteo_response

NOW = hour_floor(datetime.now(UTC))


@respx.mock
def test_batches_locations_normalizes_units_and_caches():
    route = respx.get(settings.OPEN_METEO_URL).mock(
        side_effect=lambda request: open_meteo_response(request, wind=38, snow_cm=2.54)
    )
    points = [(-105.0, 39.7), (-105.04, 39.71), (-106.8, 40.5)]  # first two share a 0.1° cell

    found = weather.forecasts(points)
    sample = weather.sample_at(found, points[0], NOW)

    assert route.call_count == 1
    assert route.calls[0].request.url.params["latitude"] == "39.7,40.5"
    assert sample.wind_mph == 38
    assert sample.snow_in_hr == pytest.approx(1.0)  # 2.54 cm → 1 in
    assert sample.forecast_time == NOW

    weather.forecasts(points)
    assert route.call_count == 1  # served from cache


@respx.mock
def test_hour_outside_forecast_is_missing_not_low():
    respx.get(settings.OPEN_METEO_URL).mock(side_effect=open_meteo_response)
    found = weather.forecasts([(-105.0, 39.7)])
    sample = weather.sample_at(found, (-105.0, 39.7), datetime(2030, 1, 1, tzinfo=UTC))
    assert sample.wind_mph is None


@respx.mock
def test_null_values_stay_none():
    def response(request):
        body = open_meteo_response(request).json()
        body["hourly"]["rain"][1] = None
        return httpx.Response(200, json=body)

    respx.get(settings.OPEN_METEO_URL).mock(side_effect=response)
    found = weather.forecasts([(-105.0, 39.7)])
    assert weather.sample_at(found, (-105.0, 39.7), NOW).rain_in_hr is None


@respx.mock
def test_failures_raise_typed_errors_and_are_not_cached():
    route = respx.get(settings.OPEN_METEO_URL)
    route.mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(ProviderTimeout):
        weather.forecasts([(-105.0, 39.7)])

    route.mock(return_value=httpx.Response(200, json={"unexpected": True}))
    with pytest.raises(ProviderError):
        weather.forecasts([(-105.0, 39.7)])

    route.mock(side_effect=open_meteo_response)
    assert weather.forecasts([(-105.0, 39.7)])  # recovers: nothing bad was cached
