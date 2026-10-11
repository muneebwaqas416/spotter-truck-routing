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
def test_missing_alternatives_use_closest_valid_detours():
    primary = here_route([DENVER, (41.3, -105.6), SLC], 9 * 3600, 880_000)  # ~547 mi
    near = here_route([DENVER, (40.5, -106.8), SLC], 9 * 3600, 900_000)  # +2%
    absurd = here_route([DENVER, (38.0, -108.0), SLC], 20 * 3600, 1_400_000)  # +59%: rejected
    farther = here_route([DENVER, (39.1, -108.5), SLC], 10 * 3600, 1_000_000)  # +14%
    route = respx.get(settings.HERE_ROUTING_URL).mock(
        side_effect=[
            httpx.Response(200, json={"routes": [primary]}),
            httpx.Response(200, json={"routes": [near]}),
            httpx.Response(200, json={"routes": [absurd]}),
            httpx.Response(200, json={"routes": [farther]}),
        ]
    )

    paths = here.routes(ORIGIN, DESTINATION, DEPARTURE, 42_000)

    assert [round(p.distance_mi) for p in paths] == [547, 559, 621]
    assert [p.is_fallback_alternative for p in paths] == [False, True, True]
    # Closer waypoints (8% offset) are requested before farther ones (15%).
    offsets = [_via_offset(call.request) for call in route.calls[1:]]
    assert offsets[0] == pytest.approx(offsets[1])  # both sides at 8%
    assert offsets[2] > offsets[0]  # then 15%


def _via_offset(request: httpx.Request) -> float:
    lat, lng = (float(v) for v in request.url.params["via"].split("!")[0].split(","))
    mid_lng, mid_lat = -105.6, 41.3  # primary route's middle vertex
    return ((lat - mid_lat) ** 2 + (lng - mid_lng) ** 2) ** 0.5


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
