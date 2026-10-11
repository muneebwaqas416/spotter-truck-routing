"""Regression tests from the Salt Lake City → Cheyenne investigation (45,001 lb, 10-mile interval).

Each test pins a behaviour that was traced in the live output, so a change to it is deliberate.
"""

from datetime import UTC, datetime

import pytest

from routing.services.domain import Checkpoint, WeatherSample
from routing.services.risk import RiskLevel, assess
from routing.services.scoring import explain, rank, route_metrics, why_not

LOAD = 45_001
T0 = datetime(2026, 10, 11, tzinfo=UTC)


def checkpoints(levels: list[RiskLevel], interval: float = 10) -> list[Checkpoint]:
    return [
        Checkpoint(index=i + 1, position=(0, 0), mile=i * interval, eta=T0, level=level)
        for i, level in enumerate(levels)
    ]


# --- Risk: sustained wind is scored; gusts are displayed only (documented decision) -------------


def test_sustained_29_5_mph_with_45_6_gusts_is_moderate():
    # Route A checkpoint 25 near Rock Springs: sustained 29.5 mph, gusts 45.6 mph.
    level, reasons = assess(WeatherSample(None, 29.5, 45.6, 0.0, 0.0), LOAD)
    assert level == RiskLevel.MODERATE
    assert reasons == ["Wind 30 mph"]


@pytest.mark.parametrize(
    ("wind", "expected"),
    [(34.9, RiskLevel.MODERATE), (35, RiskLevel.SEVERE), (45, RiskLevel.NO_TRAVEL)],
)
def test_45001_lb_triggers_both_load_overrides(wind, expected):
    assert assess(WeatherSample(None, wind, wind, 0.0, 0.0), LOAD)[0] == expected


# --- Scoring: Route A's 30 Moderate miles ------------------------------------------------------


def test_thirty_moderate_miles_over_440_gives_average_0_068():
    levels = [RiskLevel.LOW] * 23 + [RiskLevel.MODERATE] * 2 + [RiskLevel.LOW] * 20
    metrics = route_metrics(checkpoints(levels), distance_mi=440, duration_s=6.86 * 3600)
    assert metrics.miles_by_level["MODERATE"] == 30  # stretches 22-23, 23-24, 24-25
    assert metrics.avg_risk == pytest.approx(30 / 440)
    assert metrics.miles_by_level["HIGH"] == metrics.miles_by_level["SEVERE"] == 0


def test_faster_route_with_moderate_miles_loses_and_says_why():
    a = route_metrics(
        checkpoints([RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.MODERATE, RiskLevel.LOW]),
        30,
        6.86 * 3600,
    )
    b = route_metrics(checkpoints([RiskLevel.LOW] * 4), 30, 9.79 * 3600)
    c = route_metrics(checkpoints([RiskLevel.LOW] * 4), 30, 10.16 * 3600)

    assert rank({"A": a, "B": b, "C": c}) == ["B", "C", "A"]
    assert explain(b, c, "Route C") == "Same weather risk as Route C, and faster."
    assert why_not(c, b, "Route B") == "Same weather risk as Route B, but 22 min slower."
    assert why_not(a, b, "Route B") == (
        # Every stretch touches a Moderate checkpoint, so all 30 miles count as Moderate.
        "Higher average risk (1.00 vs 0.00 on Route B): 30 Moderate miles. "
        "Safety ranks ahead of time, though it is 2 h 56 min faster."
    )


def test_why_not_names_severity_before_average():
    severe = route_metrics(checkpoints([RiskLevel.LOW, RiskLevel.SEVERE]), 10, 3600)
    clean = route_metrics(checkpoints([RiskLevel.LOW, RiskLevel.LOW]), 10, 7200)
    assert why_not(severe, clean, "Route B") == (
        "More Severe miles: 10 vs 0 on Route B. "
        "Safety ranks ahead of time, though it is 1 h faster."
    )
