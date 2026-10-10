"""Checkpoint sampling along a route and arrival-time (ETA) estimation. Pure functions."""

import math
from bisect import bisect_left
from datetime import datetime, timedelta
from itertools import pairwise

from .domain import Checkpoint, LngLat, RoutePath

EARTH_RADIUS_MI = 3958.8


def haversine_mi(a: LngLat, b: LngLat) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


def cumulative_miles(coordinates: list[LngLat], total_mi: float) -> list[float]:
    """Distance along the polyline at each vertex, scaled so the end matches the route length."""
    cumulative = [0.0]
    for a, b in pairwise(coordinates):
        cumulative.append(cumulative[-1] + haversine_mi(a, b))
    geometric = cumulative[-1]
    scale = total_mi / geometric if geometric > 0 else 0.0
    return [mi * scale for mi in cumulative]


def sample_checkpoints(route: RoutePath, interval_mi: int, departure: datetime) -> list[Checkpoint]:
    """Checkpoints at 0, N, 2N, … miles plus the destination, each with its ETA.

    ETAs come from the provider's per-vertex elapsed times, so slow stretches (cities,
    mountain grades) are reflected, rather than assuming constant speed.
    """
    miles = cumulative_miles(route.coordinates, route.distance_mi)
    marks = [float(m) for m in range(0, math.ceil(route.distance_mi), interval_mi)]
    if not marks or marks[-1] < route.distance_mi:
        marks.append(route.distance_mi)

    checkpoints = []
    for index, mile in enumerate(marks, start=1):
        position, elapsed = _interpolate(route, miles, mile)
        checkpoints.append(
            Checkpoint(
                index=index,
                position=position,
                mile=mile,
                eta=departure + timedelta(seconds=elapsed),
            )
        )
    return checkpoints


def _interpolate(route: RoutePath, miles: list[float], target: float) -> tuple[LngLat, float]:
    """Position and elapsed seconds at `target` miles along the route."""
    i = bisect_left(miles, target)
    if i <= 0:
        return route.coordinates[0], route.elapsed_s[0]
    if i >= len(miles):
        return route.coordinates[-1], route.elapsed_s[-1]
    span = miles[i] - miles[i - 1]
    t = (target - miles[i - 1]) / span if span > 0 else 0.0
    (lon1, lat1), (lon2, lat2) = route.coordinates[i - 1], route.coordinates[i]
    position = (lon1 + (lon2 - lon1) * t, lat1 + (lat2 - lat1) * t)
    elapsed = route.elapsed_s[i - 1] + (route.elapsed_s[i] - route.elapsed_s[i - 1]) * t
    return position, elapsed
