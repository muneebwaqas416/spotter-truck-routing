"""Orchestrates one analysis: geocode → routes → checkpoints → weather → risk → ranking."""

from dataclasses import dataclass, replace
from datetime import datetime
from string import ascii_uppercase

from routing.exceptions import PlaceNotFound

from . import here, timezones, weather
from .checkpoints import sample_checkpoints
from .domain import Checkpoint, Place, RoutePath
from .risk import assess
from .scoring import RouteMetrics, explain, rank, route_metrics, why_not


@dataclass(frozen=True)
class AnalyzedRoute:
    id: str
    label: str
    path: RoutePath
    checkpoints: list[Checkpoint]
    metrics: RouteMetrics


@dataclass(frozen=True)
class Analysis:
    origin: Place
    destination: Place
    departure: datetime
    load_lb: int
    interval_mi: int
    routes: list[AnalyzedRoute]
    recommended_route_id: str
    reason: str
    # route id → why it ranked below the recommendation (absent for the recommended route)
    ranking_notes: dict[str, str]
    forecast_fetched_at: datetime | None


def analyze(
    origin_query: str, destination_query: str, departure: datetime, load_lb: int, interval_mi: int
) -> Analysis:
    origin = _geocode(origin_query, "origin")
    destination = _geocode(destination_query, "destination")
    # Wall-clock departures are local to the origin; check the window once the zone is known.
    departure = timezones.localize(departure, origin.time_zone)
    timezones.check_departure_window(departure)
    paths = here.routes(origin, destination, departure, load_lb)

    sampled = [sample_checkpoints(path, interval_mi, departure) for path in paths]
    found = weather.forecasts(c.position for checkpoints in sampled for c in checkpoints)

    routes = []
    for letter, path, checkpoints in zip(ascii_uppercase, paths, sampled, strict=False):
        scored = [_score(c, found, load_lb) for c in checkpoints]
        routes.append(
            AnalyzedRoute(
                id=letter,
                # Generated detours are labelled so they never pass as provider alternatives.
                label=f"Route {letter} (detour)"
                if path.is_fallback_alternative
                else f"Route {letter}",
                path=path,
                checkpoints=scored,
                metrics=route_metrics(scored, path.distance_mi, path.duration_s),
            )
        )

    order = rank({route.id: route.metrics for route in routes})
    by_id = {route.id: route for route in routes}
    best = by_id[order[0]]
    runner_up = by_id[order[1]] if len(order) > 1 else None

    return Analysis(
        origin=origin,
        destination=destination,
        departure=departure,
        load_lb=load_lb,
        interval_mi=interval_mi,
        routes=routes,
        recommended_route_id=best.id,
        reason=explain(
            best.metrics, runner_up and runner_up.metrics, runner_up.label if runner_up else ""
        ),
        ranking_notes={
            route_id: why_not(by_id[route_id].metrics, best.metrics, best.label)
            for route_id in order[1:]
        },
        forecast_fetched_at=min((f.fetched_at for f in found.values()), default=None),
    )


def _geocode(query: str, field: str) -> Place:
    try:
        return here.geocode(query)
    except PlaceNotFound as exc:
        raise PlaceNotFound(query, field) from exc


def _score(checkpoint: Checkpoint, found: dict, load_lb: int) -> Checkpoint:
    sample = weather.sample_at(found, checkpoint.position, checkpoint.eta)
    level, reasons = assess(sample, load_lb)
    return replace(checkpoint, weather=sample, level=level, reasons=reasons)
