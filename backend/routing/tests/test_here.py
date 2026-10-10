from datetime import UTC, datetime

import httpx
import pytest
import respx
from django.conf import settings

from routing.exceptions import NoRouteFound, PlaceNotFound, ProviderError
from routing.services import here
from routing.services.domain import Place
from routing.tests.conftest import DENVER, SLC, here_route, three_routes

ORIGIN = Place("Denver", (DENVER[1], DENVER[0]))
DESTINATION = Place("Salt Lake City", (SLC[1], SLC[0]))
DEPARTURE = datetime(2026, 10, 10, 12, 30, tzinfo=UTC)


@respx.mock
def test_geocode_returns_place_and_caches():
    route = respx.get(settings.HERE_GEOCODE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "address": {"label": "Denver, CO, USA"},
                        "position": {"lat": 39.7, "lng": -105},
                    }
                ]
            },
        )
    )
    assert here.geocode("Denver") == Place("Denver, CO, USA", (-105, 39.7))
    assert here.geocode("  denver ") == Place("Denver, CO, USA", (-105, 39.7))
    assert route.call_count == 1


@respx.mock
def test_geocode_not_found_is_not_cached():
    route = respx.get(settings.HERE_GEOCODE_URL).mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    with pytest.raises(PlaceNotFound):
        here.geocode("Nowhere")
    with pytest.raises(PlaceNotFound):
        here.geocode("Nowhere")
    assert route.call_count == 2


@respx.mock
def test_routes_parse_truck_alternatives_with_timings():
    route = respx.get(settings.HERE_ROUTING_URL).mock(
        return_value=httpx.Response(200, json=three_routes())
    )

    paths = here.routes(ORIGIN, DESTINATION, DEPARTURE, 42_000)

    assert len(paths) == 3
    params = route.calls[0].request.url.params
    assert params["transportMode"] == "truck"
    assert params["alternatives"] == "2"
    assert params["vehicle[grossWeight]"] == str(
        round(75_000 * 0.45359237)
    )  # 30k tare + 42k → 75k bucket
    first = paths[0]
    assert first.coordinates[0] == pytest.approx((DENVER[1], DENVER[0]), abs=1e-5)
    assert first.elapsed_s[0] == 0 and first.elapsed_s[-1] == pytest.approx(9 * 3600)
    assert first.distance_mi == pytest.approx(880_000 / 1609.344)


@respx.mock
def test_missing_alternatives_are_filled_with_detours():
    single = {"routes": three_routes()["routes"][:1]}
    detour = {"routes": three_routes()["routes"][1:2]}
    route = respx.get(settings.HERE_ROUTING_URL).mock(
        side_effect=[
            httpx.Response(200, json=single),
            httpx.Response(200, json=detour),
            httpx.Response(200, json=single),
        ]
    )

    paths = here.routes(ORIGIN, DESTINATION, DEPARTURE, 42_000)

    assert [p.is_fallback_alternative for p in paths] == [False, True]  # duplicate detour dropped
    assert "via" in route.calls[1].request.url.params


@respx.mock
def test_no_route_and_missing_key():
    respx.get(settings.HERE_ROUTING_URL).mock(return_value=httpx.Response(200, json={"routes": []}))
    with pytest.raises(NoRouteFound):
        here.routes(ORIGIN, DESTINATION, DEPARTURE, 1)

    settings.HERE_API_KEY = ""
    with pytest.raises(ProviderError):
        here.geocode("Denver")


def test_vertex_times_follow_span_durations():
    # Two equal-length spans; the first is three times slower.
    coords = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
    spans = [{"offset": 0, "duration": 300}, {"offset": 1, "duration": 100}]
    assert here._vertex_times(coords, spans, 400) == pytest.approx([0, 300, 400])


def test_route_payload_omitted_from_parse_errors():
    with pytest.raises(KeyError):
        here._parse_route({"sections": [{"summary": {}}]})


def test_here_route_fixture_roundtrip():
    path = here._parse_route(here_route([(0, 0), (0, 1)], 60, 1000))
    assert path.coordinates == [pytest.approx((0, 0)), pytest.approx((1, 0))]
