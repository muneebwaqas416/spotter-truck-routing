"""Per-route risk metrics and deterministic ranking. Pure functions.

Routes are ranked lexicographically, never by a weighted sum, so a route with more Severe
miles can never win on travel time:
    (no_travel_mi, severe_mi, high_mi, unknown_mi, avg_risk, duration_s)
"""

import math
from dataclasses import dataclass
from itertools import pairwise

from .domain import Checkpoint
from .risk import RiskLevel

UNKNOWN = "UNKNOWN"
LEVEL_KEYS = [level.name for level in RiskLevel] + [UNKNOWN]


@dataclass(frozen=True)
class RouteMetrics:
    distance_mi: float
    duration_s: float
    miles_by_level: dict[str, float]
    avg_risk: float | None  # distance-weighted over known miles


def route_metrics(
    checkpoints: list[Checkpoint], distance_mi: float, duration_s: float
) -> RouteMetrics:
    """Each stretch between checkpoints counts its miles at the worse of its two ends.

    Conservative by design, and it handles a final stretch shorter than the interval.
    A stretch touching an unknown checkpoint is unknown.
    """
    miles = dict.fromkeys(LEVEL_KEYS, 0.0)
    weighted = 0.0
    known = 0.0
    for a, b in pairwise(checkpoints):
        length = b.mile - a.mile
        if a.level is None or b.level is None:
            miles[UNKNOWN] += length
            continue
        level = RiskLevel(max(a.level, b.level))
        miles[level.name] += length
        weighted += level * length
        known += length
    return RouteMetrics(
        distance_mi=distance_mi,
        duration_s=duration_s,
        miles_by_level=miles,
        avg_risk=weighted / known if known > 0 else None,
    )


# (field label, value getter) in ranking priority order.
CRITERIA = [
    ("No Travel miles", lambda m: m.miles_by_level["NO_TRAVEL"]),
    ("Severe miles", lambda m: m.miles_by_level["SEVERE"]),
    ("High miles", lambda m: m.miles_by_level["HIGH"]),
    ("miles of unknown weather", lambda m: m.miles_by_level[UNKNOWN]),
    ("average risk", lambda m: m.avg_risk if m.avg_risk is not None else math.inf),
    ("travel time", lambda m: m.duration_s),
]


def rank_key(metrics: RouteMetrics) -> tuple[float, ...]:
    return tuple(getter(metrics) for _, getter in CRITERIA)


def rank(metrics_by_route: dict[str, RouteMetrics]) -> list[str]:
    """Route ids, best first. Ties keep the provider's order (stable sort)."""
    return sorted(metrics_by_route, key=lambda route_id: rank_key(metrics_by_route[route_id]))


def explain(best: RouteMetrics, runner_up: RouteMetrics | None, runner_up_label: str) -> str:
    """One sentence naming the criterion that decided the ranking."""
    if runner_up is None:
        return "Only one route was available."
    for label, getter in CRITERIA:
        ours, theirs = getter(best), getter(runner_up)
        if ours != theirs:
            if label == "travel time":
                return f"Same weather risk as {runner_up_label}, and faster."
            if label == "average risk":
                return f"Lower average risk ({ours:.2f} vs {theirs:.2f} on {runner_up_label})."
            return f"Fewer {label}: {ours:.0f} vs {theirs:.0f} on {runner_up_label}."
    return f"Equivalent to {runner_up_label}."
