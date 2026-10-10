from datetime import timedelta

import httpx
import pytest
import respx
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from routing.tests.conftest import open_meteo_response, three_routes

PLACES = {
    "Denver, CO": {"label": "Denver, CO, USA", "position": {"lat": 39.7392, "lng": -104.9903}},
    "Salt Lake City, UT": {
        "label": "Salt Lake City, UT, USA",
        "position": {"lat": 40.7608, "lng": -111.891},
    },
}


def geocode_response(request: httpx.Request) -> httpx.Response:
    place = PLACES.get(request.url.params["q"])
    items = [{"address": {"label": place["label"]}, "position": place["position"]}] if place else []
    return httpx.Response(200, json={"items": items})


@pytest.fixture
def providers():
    with respx.mock:
        respx.get(settings.HERE_GEOCODE_URL).mock(side_effect=geocode_response)
        routing = respx.get(settings.HERE_ROUTING_URL).mock(
            return_value=httpx.Response(200, json=three_routes())
        )
        weather = respx.get(settings.OPEN_METEO_URL).mock(
            side_effect=lambda request: open_meteo_response(request, wind=38)
        )
        yield {"routing": routing, "weather": weather}


def payload(**overrides):
    body = {
        "origin": "Denver, CO",
        "destination": "Salt Lake City, UT",
        "departure_time": (timezone.now() + timedelta(hours=1)).isoformat(),
        "load_lb": 42_000,
        "interval_mi": 25,
    }
    return {**body, **overrides}


def analyze(body):
    return APIClient().post(reverse("routing:analyze"), body, format="json")


def test_health_returns_ok():
    response = APIClient().get(reverse("routing:health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_returns_routes_checkpoints_and_recommendation(providers):
    response = analyze(payload())

    assert response.status_code == 200
    body = response.json()
    assert len(body["routes"]) == 3
    route = body["routes"][0]
    assert route["checkpoints"][0]["mile"] == 0
    assert route["checkpoints"][-1]["mile"] == route["metrics"]["distance_mi"]
    # 38 mph sustained wind with 42,000 lb → Severe by the load rule.
    assert {c["risk"] for c in route["checkpoints"]} == {"SEVERE"}
    assert route["checkpoints"][0]["reasons"] == ["Wind 38 mph with load > 40,000 lb"]
    # Equal risk everywhere, so the fastest route (B) wins on travel time.
    assert body["recommendation"]["route_id"] == "B"
    assert body["forecast_fetched_at"] is not None
    assert providers["weather"].call_count == 1  # every checkpoint in one batched call


def test_repeat_analysis_with_different_load_reuses_provider_data(providers):
    analyze(payload())
    response = analyze(payload(load_lb=20_000))

    assert response.status_code == 200
    assert response.json()["routes"][0]["checkpoints"][0]["risk"] == "HIGH"  # rules recomputed
    assert providers["routing"].call_count == 2  # different weight bucket → new route call
    assert providers["weather"].call_count == 1  # weather served from cache


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"interval_mi": 15}, "interval_mi"),
        ({"load_lb": 0}, "load_lb"),
        ({"load_lb": 80_001}, "load_lb"),
        ({"departure_time": "2026-10-10T06:00:00"}, "departure_time"),  # naive
        ({"departure_time": (timezone.now() + timedelta(days=17)).isoformat()}, "departure_time"),
        ({"destination": "denver, co"}, "destination"),
        ({"origin": ""}, "origin"),
    ],
)
def test_invalid_input_returns_field_errors(overrides, field):
    response = analyze(payload(**overrides))
    assert response.status_code == 400
    assert field in response.json()


def test_unknown_place_maps_to_field_error(providers):
    response = analyze(payload(destination="Atlantis"))
    assert response.status_code == 400
    assert response.json()["code"] == "place_not_found"
    assert "destination" in response.json()


def test_weather_timeout_returns_504_without_internals(providers):
    providers["weather"].mock(side_effect=httpx.ReadTimeout("slow"))
    response = analyze(payload())
    assert response.status_code == 504
    assert response.json() == {
        "code": "provider_timeout",
        "detail": "The weather service is unavailable.",
    }


def test_routing_error_returns_502(providers):
    providers["routing"].mock(return_value=httpx.Response(500))
    response = analyze(payload())
    assert response.status_code == 502
    assert response.json()["code"] == "provider_error"


def test_heatmap_returns_grid_for_49_hours(providers):
    response = APIClient().get(
        reverse("routing:heatmap"),
        {"bbox": "-112,39,-104.5,41.5", "start": timezone.now().isoformat(), "load_lb": 42_000},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["hours"]) == 49
    assert len(body["scores"][0]) == len(body["points"]) <= 260
    assert body["scores"][0][0] == 3  # Severe


@pytest.mark.parametrize("bbox", ["1,2,3", "-104,39,-112,41", "-140,20,-100,50"])
def test_heatmap_rejects_bad_bbox(bbox):
    response = APIClient().get(
        reverse("routing:heatmap"), {"bbox": bbox, "start": timezone.now().isoformat()}
    )
    assert response.status_code == 400


def test_geocode_suggestions(providers):
    respx.get(settings.HERE_AUTOSUGGEST_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "1",
                        "title": "Denver",
                        "address": {"label": "Denver, CO, USA"},
                        "position": {"lat": 39.7, "lng": -105},
                    },
                    {"id": "2", "title": "Coffee shops"},  # no position → skipped
                ]
            },
        )
    )
    response = APIClient().get(reverse("routing:geocode"), {"q": "Denver"})
    assert response.status_code == 200
    assert response.json() == [{"id": "1", "label": "Denver, CO, USA", "position": [-105, 39.7]}]
