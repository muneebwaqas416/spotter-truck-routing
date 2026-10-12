from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from routing.services.heatmap import MAX_POINTS
from routing.tests.conftest import open_meteo_response, three_routes

PLACES = {
    "Denver, CO": {"label": "Denver, CO, USA", "position": {"lat": 39.7392, "lng": -104.9903}},
    "Salt Lake City, UT": {
        "label": "Salt Lake City, UT, USA",
        "position": {"lat": 40.7608, "lng": -111.891},
    },
}
DENVER_TZ = "America/Denver"


def geocode_response(request: httpx.Request) -> httpx.Response:
    place = PLACES.get(request.url.params["q"])
    timezone_info = {"name": DENVER_TZ, "utcOffset": "-06:00"}
    items = (
        [
            {
                "address": {"label": place["label"]},
                "position": place["position"],
                "timeZone": timezone_info,
            }
        ]
        if place
        else []
    )
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
        ({"departure_time": "not-a-date"}, "departure_time"),
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


@pytest.mark.parametrize(("retry_after", "expected"), [(None, "60"), ("30", "30")])
def test_weather_rate_limit_returns_503_with_retry_after(providers, retry_after, expected):
    """Open-Meteo's per-minute limit is temporary: tell the client to wait, not that it's down."""
    headers = {"Retry-After": retry_after} if retry_after else {}
    providers["weather"].mock(return_value=httpx.Response(429, headers=headers))
    response = analyze(payload())
    assert response.status_code == 503
    assert response["Retry-After"] == expected
    assert response.json() == {
        "code": "provider_busy",
        "detail": "The weather service is busy. Try again in a minute.",
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


@pytest.mark.parametrize("bbox", ["1,2,3", "-104,39,-112,41", "-170,10,-50,70"])
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


def test_naive_departure_is_local_time_at_origin(providers):
    """06:00 entered for Denver means 06:00 Mountain time, not the server's or browser's zone."""
    local = (timezone.now() + timedelta(days=1)).astimezone(ZoneInfo(DENVER_TZ))
    wall_clock = local.replace(hour=6, minute=0, second=0, microsecond=0, tzinfo=None)

    response = analyze(payload(departure_time=wall_clock.isoformat()))

    assert response.status_code == 200
    body = response.json()
    departure = datetime.fromisoformat(body["departure_time"])
    assert departure.utcoffset() in (timedelta(hours=-6), timedelta(hours=-7))  # MDT / MST
    assert departure.hour == 6
    assert body["origin"]["time_zone"] == DENVER_TZ
    first_eta = datetime.fromisoformat(body["routes"][0]["checkpoints"][0]["eta"])
    assert first_eta == departure  # same instant, whatever offset it's written with


def test_departure_outside_forecast_window_is_a_field_error(providers):
    too_far = (timezone.now() + timedelta(days=15)).isoformat()
    response = analyze(payload(departure_time=too_far))
    assert response.status_code == 400
    [message] = response.json()["departure_time"]
    assert message.startswith("Forecasts only reach")


def test_routes_carry_ranking_notes_and_detour_labels(providers):
    providers["routing"].mock(
        side_effect=[
            httpx.Response(200, json={"routes": three_routes()["routes"][:1]}),
            httpx.Response(200, json={"routes": three_routes()["routes"][1:2]}),
            httpx.Response(200, json={"routes": three_routes()["routes"][2:3]}),
        ]
    )
    body = analyze(payload()).json()

    labels = {route["id"]: route["label"] for route in body["routes"]}
    assert labels == {"A": "Route A", "B": "Route B (detour)", "C": "Route C (detour)"}
    best = body["recommendation"]["route_id"]
    notes = {route["id"]: route["ranking_note"] for route in body["routes"]}
    assert notes[best] is None
    assert all(note for route_id, note in notes.items() if route_id != best)


def test_heatmap_accepts_cross_country_corridor(providers):
    """Regression: Denver → East Coast (31.8° wide) was rejected by a 20° area limit."""
    response = APIClient().get(
        reverse("routing:heatmap"),
        {"bbox": "-105.34,38.25,-73.51,42.26", "start": timezone.now().isoformat()},
    )
    assert response.status_code == 200
    assert len(response.json()["points"]) <= MAX_POINTS


@pytest.mark.parametrize(
    "start",
    [
        "9999-12-31T23:00:00Z",
        (timezone.now() + timedelta(days=20)).isoformat(),
        "2020-01-01T00:00:00Z",
    ],
)
def test_heatmap_start_outside_forecast_is_a_field_error(start):
    """Regression: year 9999 crashed with a 500 (OverflowError)."""
    response = APIClient().get(
        reverse("routing:heatmap"), {"bbox": "-105,39,-104,40", "start": start}
    )
    assert response.status_code == 400
    assert "start" in response.json()


# --- QA review: provider failures stay clean JSON errors -------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"items": [{"position": {"lat": 39.7, "lng": -105.0}}]},  # no address
        [{"unexpected": "list"}],
        {"items": [{"address": {"label": "Denver"}, "position": "39.7,-105"}]},
    ],
)
def test_malformed_geocode_returns_502(providers, body):
    respx.get(settings.HERE_GEOCODE_URL).mock(return_value=httpx.Response(200, json=body))
    response = analyze(payload())
    assert response.status_code == 502
    assert response.json()["code"] == "provider_error"


def test_malformed_suggestion_returns_502(providers):
    respx.get(settings.HERE_AUTOSUGGEST_URL).mock(
        return_value=httpx.Response(
            200, json={"items": [{"id": "1", "position": {"lat": 1, "lng": 2}}]}
        )
    )
    response = APIClient().get(reverse("routing:geocode"), {"q": "Denver"})
    assert response.status_code == 502


def test_route_body_that_is_a_list_returns_502(providers):
    providers["routing"].mock(return_value=httpx.Response(200, json=[{"routes": []}]))
    assert analyze(payload()).status_code == 502


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda hourly: hourly.update(wind_gusts_10m=hourly["wind_gusts_10m"][:-5]),
        lambda hourly: hourly.update(wind_speed_10m=None),
        lambda hourly: hourly.update(wind_speed_10m=["fast"] * len(hourly["time"])),
    ],
)
def test_malformed_weather_series_returns_502(providers, corrupt):
    def response(request):
        body = open_meteo_response(request).json()
        for location in body if isinstance(body, list) else [body]:
            corrupt(location["hourly"])
        return httpx.Response(200, json=body)

    providers["weather"].mock(side_effect=response)
    assert analyze(payload()).status_code == 502


def test_failed_detour_request_keeps_the_provider_route(providers):
    """Regression: a timeout while generating detours turned a good route into a 504."""
    providers["routing"].mock(
        side_effect=[
            httpx.Response(200, json={"routes": three_routes()["routes"][:1]}),
            httpx.ReadTimeout("slow"),
        ]
    )
    response = analyze(payload())
    assert response.status_code == 200
    assert [route["label"] for route in response.json()["routes"]] == ["Route A"]


def test_same_place_under_two_spellings_is_a_field_error(providers):
    PLACES["Denver"] = PLACES["Denver, CO"]
    try:
        response = analyze(payload(destination="Denver"))
    finally:
        del PLACES["Denver"]
    assert response.status_code == 400
    assert response.json() == {"destination": ["Origin and destination are the same place."]}


def test_provider_error_bodies_are_not_logged(providers, caplog):
    providers["routing"].mock(return_value=httpx.Response(500, text="echo apiKey=secret-value"))
    analyze(payload())
    assert "HTTP 500" in caplog.text
    assert "secret-value" not in caplog.text


def test_departure_now_uses_the_current_time_at_the_origin(providers):
    """The browser doesn't know the origin's zone, so "now" is resolved on the server."""
    before = timezone.now()
    response = analyze(payload(departure_time="now"))
    assert response.status_code == 200
    departure = datetime.fromisoformat(response.json()["departure_time"])
    assert before - timedelta(seconds=1) <= departure <= timezone.now()
    assert departure.utcoffset() in (timedelta(hours=-6), timedelta(hours=-7))  # Denver
