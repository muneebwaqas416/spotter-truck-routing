"""Regression tests from the Salt Lake City → Cheyenne investigation (45,001 lb, 10-mile interval).

Each test pins a behaviour that was traced in the live output, so a change to it is deliberate.
"""

from datetime import UTC, datetime, timedelta
from itertools import pairwise

import pytest

from routing.services import weather
from routing.services.domain import Checkpoint, Place, RoutePath, WeatherSample
from routing.services.heatmap import MAX_POINTS, _grid
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
    assert reasons == ["Wind 29.5 mph"]


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


@pytest.mark.parametrize(
    "bbox",
    [
        (-105.34, 38.25, -73.51, 42.26),
        (-125, 25, -66, 49),
        (-112, 39, -104.5, 41.5),
        (0, 0, 0.5, 0.5),
    ],
)
def test_heatmap_grid_never_exceeds_point_cap(bbox):
    points = _grid(bbox)
    assert 0 < len(points) <= MAX_POINTS


# --- QA review: DST, float boundaries, nearest hour ------------------------------------------


def test_eta_adds_real_elapsed_time_across_dst(monkeypatch):
    """Regression: 4 h after 00:00 MDT on the fall-back night is 10:00 UTC, not 11:00."""
    from routing.services import analysis

    monkeypatch.setattr(analysis.timezones, "check_departure_window", lambda departure: None)
    captured = {}

    def fake_routes(origin, destination, start, load_lb):
        captured["start"] = start
        return [_straight_route(hours=4)]

    positions = {"A": (-105.0, 39.7), "B": (-104.0, 39.7)}
    monkeypatch.setattr(analysis.here, "geocode", lambda q: Place(q, positions[q], DENVER_TZ))
    monkeypatch.setattr(analysis.here, "routes", fake_routes)
    monkeypatch.setattr(analysis.weather, "forecasts", lambda positions: {})

    result = analysis.analyze("A", "B", datetime(2026, 11, 1, 0, 0), 20_000, 50)

    assert result.departure.utcoffset() == timedelta(hours=-6)  # still shown as MDT
    arrival = result.routes[0].checkpoints[-1].eta
    assert arrival.astimezone(UTC) == datetime(2026, 11, 1, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("rain", "showers", "expected"),
    [
        (0.01, 0.09, RiskLevel.MODERATE),
        (0.009, 0.091, RiskLevel.MODERATE),
        (0.2, 0.05, RiskLevel.HIGH),
    ],
)
def test_rain_plus_showers_on_a_threshold_is_not_understated(rain, showers, expected):
    forecast = weather._parse(_open_meteo_location(rain=rain, showers=showers))
    assert assess(forecast.at(T0), LOAD)[0] == expected


@pytest.mark.parametrize(
    ("snow_cm", "expected"), [(1.27, RiskLevel.MODERATE), (5.08, RiskLevel.SEVERE)]
)
def test_snow_converted_from_cm_on_a_threshold_is_not_understated(snow_cm, expected):
    forecast = weather._parse(_open_meteo_location(snow_cm=snow_cm))
    assert assess(forecast.at(T0), LOAD)[0] == expected


@pytest.mark.parametrize(("minute", "hour"), [(29, 10), (30, 11), (31, 11)])
def test_half_past_always_rounds_to_the_next_hour(minute, hour):
    forecast = weather._parse(_open_meteo_location())
    assert forecast.at(T0.replace(hour=10, minute=minute)).forecast_time.hour == hour
    assert forecast.at(T0.replace(hour=11, minute=minute)).forecast_time.hour == hour + 1


DENVER_TZ = "America/Denver"


def _straight_route(hours: float) -> RoutePath:
    coordinates = [(-105.0, 39.7), (-104.0, 39.7)]
    return RoutePath(coordinates, 53.0, hours * 3600, [0.0, hours * 3600])


def _open_meteo_location(rain=0.0, showers=0.0, snow_cm=0.0, hours=24) -> dict:
    """One location starting at T0, in the units Open-Meteo declares."""
    return {
        "hourly_units": {
            "wind_speed_10m": "mp/h",
            "rain": "inch",
            "showers": "inch",
            "snowfall": "cm",
        },
        "hourly": {
            "time": [int(T0.timestamp()) + h * 3600 for h in range(hours)],
            "wind_speed_10m": [5.0] * hours,
            "wind_gusts_10m": [7.0] * hours,
            "rain": [rain] * hours,
            "showers": [showers] * hours,
            "snowfall": [snow_cm] * hours,
        },
    }


# --- QA review: heatmap grid covers the whole corridor ---------------------------------------


@pytest.mark.parametrize(
    "bbox",
    [
        (-122.83, 25.26, -79.69, 48.11),  # Seattle-Miami: the grid stopped ~2.5° short of both
        (-118.74, 33.55, -73.5, 41.2),  # Los Angeles-New York
        (-100.0, 30.0, -99.7, 30.3),  # float noise dropped the last column
        (-112.5, 40.2, -104.3, 41.8),
        (0, 0, 0.5, 0.5),
    ],
)
def test_heatmap_grid_reaches_every_edge_on_a_regular_spacing(bbox):
    points = _grid(bbox)
    lons = sorted({lon for lon, _ in points})
    lats = sorted({lat for _, lat in points})
    step = round(lons[1] - lons[0], 1)

    assert len(points) == len(lons) * len(lats) <= MAX_POINTS
    assert all(round(b - a, 1) == step for a, b in pairwise(lons))
    assert all(round(b - a, 1) == step for a, b in pairwise(lats))
    # Each sample is drawn half a step wide, so the outer samples must reach the bbox edges.
    half = step / 2 + 1e-9
    assert lons[0] - half <= bbox[0] and lons[-1] + half >= bbox[2]
    assert lats[0] - half <= bbox[1] and lats[-1] + half >= bbox[3]


# --- QA review: displayed values never cross a threshold -------------------------------------


@pytest.mark.parametrize(
    ("sample", "load", "reason"),
    [
        (WeatherSample(None, 44.6, 50, 0.0, 0.0), 40_001, "Wind 44.6 mph with load > 40,000 lb"),
        (WeatherSample(None, 54.96, 60, 0.0, 0.0), 0, "Wind 54.9 mph"),  # Severe, not "55"
        (WeatherSample(None, 0, 0, 0.0, 1.96), 0, "Snow 1.9 in/hr"),  # High, not "2.0"
        (WeatherSample(None, 0, 0, 0.249, 0.0), 0, "Rain 0.24 in/hr"),  # Moderate, not "0.25"
        (WeatherSample(None, 0, 0, 0.29, 0.0), 0, "Rain 0.29 in/hr"),  # no float drift down
    ],
)
def test_reason_values_are_truncated_not_rounded(sample, load, reason):
    assert reason in assess(sample, load)[1]
