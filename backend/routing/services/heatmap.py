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
    """Regular grid aligned to the weather cache's 0.1° cells, at most MAX_POINTS points."""
    min_lon, min_lat, max_lon, max_lat = bbox
    area = (max_lon - min_lon) * (max_lat - min_lat)
    start_lon = round(min_lon / weather.GRID_DEG) * weather.GRID_DEG
    start_lat = round(min_lat / weather.GRID_DEG) * weather.GRID_DEG
    step = max(weather.GRID_DEG, math.ceil(math.sqrt(area / MAX_POINTS) * 10) / 10)
    # Edge rows/columns can push the count over the cap; widen the spacing until it fits.
    while (cols := int((max_lon - start_lon) / step) + 1) * (
        rows := int((max_lat - start_lat) / step) + 1
    ) > MAX_POINTS:
        step = round(step + weather.GRID_DEG, 1)
    return [
        (round(start_lon + c * step, 1), round(start_lat + r * step, 1))
        for r in range(rows)
        for c in range(cols)
    ]
