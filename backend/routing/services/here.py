"""HERE geocoding, autosuggest and truck routing. HERE's JSON never leaves this module."""

import hashlib
import math
from dataclasses import replace
from datetime import datetime
from itertools import pairwise

import flexpolyline
from django.conf import settings

from routing.cache import get_or_fetch
from routing.exceptions import NoRouteFound, PlaceNotFound, ProviderError

from .checkpoints import haversine_mi
from .domain import LngLat, Place, RoutePath, Suggestion
from .http import get_json

GEOCODE_TTL_S = 7 * 24 * 3600  # places don't move
SUGGEST_TTL_S = 24 * 3600
ROUTE_TTL_S = 6 * 3600  # road network is stable; departure hour is part of the key
COUNTRIES = "countryCode:USA,CAN,MEX"
# Autosuggest needs a search centre; the geographic centre of the contiguous US biases results
# toward North American freight geography without excluding anything inside COUNTRIES.
SUGGEST_CENTRE = "39.83,-98.58"
ROUTES_WANTED = 3
# Assumption (README): the routing weight is tractor + empty trailer + load.
TRUCK_TARE_LB = 30_000
WEIGHT_BUCKET_LB = 5_000
KG_PER_LB = 0.45359237
METERS_PER_MILE = 1609.344
# Detour waypoints sit this fraction of the trip length off the midpoint, either side.
DETOUR_OFFSET_FRACTION = 0.15


def geocode(query: str) -> Place:
    # v2: Place gained `time_zone`; old v1 entries are simply never read again.
    return get_or_fetch(_text_key("geo", query, version=2), GEOCODE_TTL_S, lambda: _geocode(query))


def suggest(query: str) -> list[Suggestion]:
    return get_or_fetch(_text_key("suggest", query), SUGGEST_TTL_S, lambda: _suggest(query))


def _text_key(kind: str, query: str, version: int = 1) -> str:
    """Case- and whitespace-insensitive key; hashed so user text is never part of a cache key."""
    normalized = " ".join(query.lower().split())
    return f"v{version}:{kind}:{hashlib.sha256(normalized.encode()).hexdigest()[:32]}"


def routes(origin: Place, destination: Place, departure: datetime, load_lb: int) -> list[RoutePath]:
    """Up to three truck routes. Missing alternatives are generated with detour waypoints."""
    gross_lb = math.ceil((TRUCK_TARE_LB + load_lb) / WEIGHT_BUCKET_LB) * WEIGHT_BUCKET_LB
    hour = departure.replace(minute=0, second=0, microsecond=0).isoformat()
    key = (
        f"v1:route:{origin.position[0]:.4f},{origin.position[1]:.4f}:"
        f"{destination.position[0]:.4f},{destination.position[1]:.4f}:{gross_lb}:{hour}"
    )
    return get_or_fetch(
        key, ROUTE_TTL_S, lambda: _routes_with_fallbacks(origin, destination, departure, gross_lb)
    )


def _api_key() -> str:
    if not settings.HERE_API_KEY:
        raise ProviderError("routing", "HERE_API_KEY is not configured")
    return settings.HERE_API_KEY


def _geocode(query: str) -> Place:
    data = get_json(
        "geocoding",
        settings.HERE_GEOCODE_URL,
        {"q": query, "in": COUNTRIES, "limit": 1, "show": "tz", "apiKey": _api_key()},
    )
    items = data.get("items") or []
    if not items:
        raise PlaceNotFound(query)
    item = items[0]
    return Place(
        label=item["address"]["label"],
        position=_lng_lat(item["position"]),
        time_zone=item.get("timeZone", {}).get("name", "UTC"),
    )


def _suggest(query: str) -> list[Suggestion]:
    data = get_json(
        "geocoding",
        settings.HERE_AUTOSUGGEST_URL,
        {"q": query, "at": SUGGEST_CENTRE, "in": COUNTRIES, "limit": 5, "apiKey": _api_key()},
    )
    return [
        Suggestion(
            id=item["id"],
            label=item.get("address", {}).get("label", item["title"]),
            position=_lng_lat(item["position"]),
        )
        for item in data.get("items", [])
        if "position" in item  # category/chain results have no single position
    ]


def _routes_with_fallbacks(
    origin: Place, destination: Place, departure: datetime, gross_lb: int
) -> list[RoutePath]:
    found = _request_routes(
        origin, destination, departure, gross_lb, alternatives=ROUTES_WANTED - 1
    )
    if not found:
        raise NoRouteFound()
    for via in _detour_waypoints(found[0]):
        if len(found) >= ROUTES_WANTED:
            break
        for path in _request_routes(origin, destination, departure, gross_lb, via=via):
            if not any(_same_route(path, existing) for existing in found):
                found.append(replace(path, is_fallback_alternative=True))
    return found[:ROUTES_WANTED]


def _request_routes(
    origin: Place,
    destination: Place,
    departure: datetime,
    gross_lb: int,
    alternatives: int = 0,
    via: LngLat | None = None,
) -> list[RoutePath]:
    params = {
        "transportMode": "truck",
        "origin": _lat_lng(origin.position),
        "destination": _lat_lng(destination.position),
        "departureTime": departure.isoformat(),
        "vehicle[grossWeight]": round(gross_lb * KG_PER_LB),
        "alternatives": alternatives,
        "return": "polyline,summary",
        "spans": "duration,length",
        "apiKey": _api_key(),
    }
    if via:
        params["via"] = f"{_lat_lng(via)}!passThrough=true"
    data = get_json("routing", settings.HERE_ROUTING_URL, params)
    try:
        return [_parse_route(route) for route in data.get("routes", [])]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ProviderError("routing", "malformed route") from exc


def _parse_route(route: dict) -> RoutePath:
    """Join a route's sections; spread each span's duration over its vertices by distance."""
    coordinates: list[LngLat] = []
    elapsed: list[float] = []
    distance_m = duration_s = 0.0
    for section in route["sections"]:
        coords = [(point[1], point[0]) for point in flexpolyline.decode(section["polyline"])]
        times = _vertex_times(coords, section.get("spans", []), section["summary"]["duration"])
        skip = 1 if coordinates else 0  # sections share their joining vertex
        coordinates += coords[skip:]
        elapsed += [duration_s + t for t in times[skip:]]
        distance_m += section["summary"]["length"]
        duration_s += section["summary"]["duration"]
    return RoutePath(coordinates, distance_m / METERS_PER_MILE, duration_s, elapsed)


def _vertex_times(coords: list[LngLat], spans: list[dict], total_s: float) -> list[float]:
    """Elapsed seconds at each vertex. Span starts are anchors; vertices between are by distance."""
    anchors = {0: 0.0, len(coords) - 1: float(total_s)}
    clock = 0.0
    for span in spans:
        anchors.setdefault(span["offset"], clock)
        clock += span.get("duration", 0)

    distance = [0.0]
    for a, b in pairwise(coords):
        distance.append(distance[-1] + haversine_mi(a, b))

    times = [0.0] * len(coords)
    points = sorted(anchors.items())
    for (i0, t0), (i1, t1) in pairwise(points):
        span_mi = distance[i1] - distance[i0]
        for i in range(i0, i1 + 1):
            share = (distance[i] - distance[i0]) / span_mi if span_mi > 0 else 0.0
            times[i] = t0 + (t1 - t0) * share
    return times


def _detour_waypoints(route: RoutePath) -> list[LngLat]:
    """Two points either side of the route's midpoint, to force genuinely different routes."""
    (lon0, lat0), (lon1, lat1) = route.coordinates[0], route.coordinates[-1]
    mid_lon, mid_lat = route.coordinates[len(route.coordinates) // 2]
    dx, dy = lon1 - lon0, lat1 - lat0
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    offset = DETOUR_OFFSET_FRACTION * length
    return [
        (mid_lon + nx * offset, mid_lat + ny * offset),
        (mid_lon - nx * offset, mid_lat - ny * offset),
    ]


def _same_route(a: RoutePath, b: RoutePath) -> bool:
    return abs(a.distance_mi - b.distance_mi) < 0.01 * max(a.distance_mi, b.distance_mi)


def _lng_lat(position: dict) -> LngLat:
    return (position["lng"], position["lat"])


def _lat_lng(position: LngLat) -> str:
    return f"{position[1]:.6f},{position[0]:.6f}"
