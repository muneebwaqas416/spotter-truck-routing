from datetime import UTC, datetime, timedelta

import pytest

from routing.services.checkpoints import haversine_mi, sample_checkpoints
from routing.services.domain import RoutePath

DEPARTURE = datetime(2026, 10, 10, 12, tzinfo=UTC)
# Due east along the equator: 1° of longitude ≈ 69.09 mi.
ONE_DEGREE_MI = haversine_mi((0, 0), (1, 0))


def straight_route(degrees: float, elapsed: list[float]) -> RoutePath:
    coords = [(i * degrees / (len(elapsed) - 1), 0.0) for i in range(len(elapsed))]
    distance = ONE_DEGREE_MI * degrees
    return RoutePath(coords, distance, elapsed[-1], elapsed)


def test_includes_start_and_destination_when_not_divisible():
    route = straight_route(1, [0, 3600])  # ~69 mi
    checkpoints = sample_checkpoints(route, 25, DEPARTURE)
    assert [round(c.mile) for c in checkpoints] == [0, 25, 50, 69]
    assert checkpoints[0].position == pytest.approx((0, 0))
    assert checkpoints[-1].position == pytest.approx((1, 0))


def test_route_shorter_than_interval_has_start_and_end():
    route = straight_route(0.1, [0, 600])  # ~7 mi
    checkpoints = sample_checkpoints(route, 50, DEPARTURE)
    assert len(checkpoints) == 2
    assert checkpoints[-1].eta == DEPARTURE + timedelta(seconds=600)


def test_eta_follows_provider_timings_not_constant_speed():
    # Two equal-length halves; the first takes 3x longer (e.g. city traffic).
    route = straight_route(2, [0, 5400, 7200])
    halfway = sample_checkpoints(route, round(ONE_DEGREE_MI), DEPARTURE)[1]
    assert halfway.mile == pytest.approx(round(ONE_DEGREE_MI))
    assert halfway.eta == pytest.approx(
        DEPARTURE + timedelta(seconds=5400), abs=timedelta(seconds=60)
    )


def test_indices_are_sequential_from_one():
    checkpoints = sample_checkpoints(straight_route(1, [0, 3600]), 10, DEPARTURE)
    assert [c.index for c in checkpoints] == list(range(1, len(checkpoints) + 1))
