"""Corridor risk grid for hours 0-48, reusing the weather cache and the same risk rules."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import weather
from .domain import LngLat
from .risk import assess

# Every point is one weather call on a cache miss, and the free tier allows 600 a minute, so a
# fresh heatmap stays well under that. ~20-40 km spacing for a typical corridor.
MAX_POINTS = 120
HOURS = 48


@dataclass(frozen=True)
class Heatmap:
    points: list[LngLat]
    hours: list[datetime]
    scores: list[list[int | None]]  # [hour][point]; None = forecast unavailable


def corridor_heatmap(
    bbox: tuple[float, float, float, float], start: datetime, load_lb: int
) -> Heatmap:
    points = _grid(bbox)
    found = weather.forecasts(points)
    first_hour = start.replace(minute=0, second=0, microsecond=0)
    hours = [first_hour + timedelta(hours=h) for h in range(HOURS + 1)]
    scores = [
        [assess(weather.sample_at(found, point, hour), load_lb)[0] for point in points]
        for hour in hours
    ]
    return Heatmap(points, hours, [[None if s is None else int(s) for s in row] for row in scores])


def _grid(bbox: tuple[float, float, float, float]) -> list[LngLat]:
    """Regular grid on the weather cache's 0.1° cells covering the whole bbox, ≤ MAX_POINTS points.

    The grid is centred on the bbox with enough rows and columns to reach both edges; the map
    draws each sample as a cell half a step wide on either side, so the bbox is fully covered.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    area = (max_lon - min_lon) * (max_lat - min_lat)
    step = max(weather.GRID_DEG, math.ceil(math.sqrt(area / MAX_POINTS) * 10) / 10)
    # Covering both edges adds a row/column; widen the spacing until the grid fits the cap.
    while (cols := _axis_count(min_lon, max_lon, step)) * (
        rows := _axis_count(min_lat, max_lat, step)
    ) > MAX_POINTS:
        step = round(step + weather.GRID_DEG, 1)
    first_lon = _axis_start(min_lon, max_lon, step, cols)
    first_lat = _axis_start(min_lat, max_lat, step, rows)
    return [
        (round(first_lon + c * step, 1), round(first_lat + r * step, 1))
        for r in range(rows)
        for c in range(cols)
    ]


def _axis_count(low: float, high: float, step: float) -> int:
    # Rounding first stops float noise (0.3 / 0.1 = 2.9999…) from dropping a sample.
    return math.ceil(round((high - low) / step, 6)) + 1


def _axis_start(low: float, high: float, step: float, count: int) -> float:
    """First sample, centred on the span and snapped to the 0.1° weather cells."""
    first = (low + high) / 2 - (count - 1) * step / 2
    return round(first / weather.GRID_DEG) * weather.GRID_DEG
