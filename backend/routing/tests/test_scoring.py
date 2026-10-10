from datetime import UTC, datetime

from routing.services.domain import Checkpoint
from routing.services.risk import RiskLevel
from routing.services.scoring import RouteMetrics, explain, rank, route_metrics

T0 = datetime(2026, 10, 10, tzinfo=UTC)


def cp(mile: float, level: RiskLevel | None) -> Checkpoint:
    return Checkpoint(index=0, position=(0, 0), mile=mile, eta=T0, level=level)


def metrics(**overrides) -> RouteMetrics:
    miles = {"LOW": 0.0, "MODERATE": 0.0, "HIGH": 0.0, "SEVERE": 0.0, "NO_TRAVEL": 0.0}
    miles["UNKNOWN"] = 0.0
    miles.update({k: v for k, v in overrides.items() if k.isupper()})
    return RouteMetrics(
        distance_mi=100,
        duration_s=overrides.get("duration", 3600),
        miles_by_level=miles,
        avg_risk=overrides.get("avg", 1.0),
    )


def test_stretch_counts_at_worse_end_including_short_final_stretch():
    m = route_metrics(
        [
            cp(0, RiskLevel.LOW),
            cp(25, RiskLevel.SEVERE),
            cp(50, RiskLevel.LOW),
            cp(60, RiskLevel.LOW),
        ],
        60,
        3600,
    )
    assert m.miles_by_level["SEVERE"] == 50
    assert m.miles_by_level["LOW"] == 10
    assert m.avg_risk == (50 * 3 + 10 * 0) / 60


def test_unknown_stretch_is_excluded_from_average():
    m = route_metrics([cp(0, RiskLevel.LOW), cp(25, None), cp(50, RiskLevel.HIGH)], 50, 3600)
    assert m.miles_by_level["UNKNOWN"] == 50
    assert m.avg_risk is None


def test_ranking_priorities_in_order():
    # Each pair differs on one criterion; the better value must win whatever comes after it.
    cases = [
        (metrics(NO_TRAVEL=0, SEVERE=90), metrics(NO_TRAVEL=10)),
        (metrics(SEVERE=0, HIGH=90), metrics(SEVERE=10)),
        (metrics(HIGH=0, UNKNOWN=90), metrics(HIGH=10)),
        (metrics(UNKNOWN=0, avg=3.5), metrics(UNKNOWN=10, avg=0.1)),
        (metrics(avg=0.5, duration=99_999), metrics(avg=1.5, duration=1)),
        (metrics(duration=100), metrics(duration=200)),
    ]
    for better, worse in cases:
        assert rank({"worse": worse, "better": better}) == ["better", "worse"]


def test_route_with_no_average_ranks_after_scored_route():
    assert rank({"a": metrics(avg=None), "b": metrics(avg=3.9)}) == ["b", "a"]


def test_explain_names_the_deciding_criterion():
    assert explain(metrics(SEVERE=0), metrics(SEVERE=50), "Route A") == (
        "Fewer Severe miles: 0 vs 50 on Route A."
    )
    assert explain(metrics(duration=1), metrics(duration=2), "Route C") == (
        "Same weather risk as Route C, and faster."
    )
