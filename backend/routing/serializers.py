"""Request validation and response representation for the routing API."""

import re
from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from routing.services.analysis import Analysis
from routing.services.checkpoints import haversine_mi
from routing.services.domain import Checkpoint, Suggestion
from routing.services.heatmap import Heatmap
from routing.services.scoring import LEVEL_KEYS

MAX_LOAD_LB = 80_000  # US federal gross weight limit
FORECAST_HORIZON_DAYS = 16
PAST_GRACE = timedelta(hours=1)
MAX_BBOX_DEGREES = 20
TZ_SUFFIX = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")

LEVEL_NAMES = LEVEL_KEYS[:-1]  # index → name for known levels


# --- Requests -----------------------------------------------------------------


class AnalyzeRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=200, trim_whitespace=True)
    destination = serializers.CharField(max_length=200, trim_whitespace=True)
    departure_time = serializers.DateTimeField()
    load_lb = serializers.IntegerField(min_value=1, max_value=MAX_LOAD_LB)
    interval_mi = serializers.ChoiceField(choices=[10, 25, 50])

    def validate_departure_time(self, value):
        # Reject naive datetimes rather than silently assuming a timezone.
        if not TZ_SUFFIX.search(str(self.initial_data.get("departure_time", ""))):
            raise serializers.ValidationError(
                "Include a timezone offset, e.g. 2026-10-10T06:00:00-06:00."
            )
        now = timezone.now()
        if value < now - PAST_GRACE:
            raise serializers.ValidationError("Departure is in the past.")
        if value > now + timedelta(days=FORECAST_HORIZON_DAYS):
            raise serializers.ValidationError(
                f"Forecasts cover the next {FORECAST_HORIZON_DAYS} days."
            )
        return value

    def validate(self, attrs):
        if attrs["origin"].lower() == attrs["destination"].lower():
            raise serializers.ValidationError(
                {"destination": "Destination must differ from origin."}
            )
        return attrs


class HeatmapQuerySerializer(serializers.Serializer):
    bbox = serializers.CharField()
    start = serializers.DateTimeField()
    load_lb = serializers.IntegerField(min_value=0, max_value=MAX_LOAD_LB, default=0)

    def validate_bbox(self, value):
        try:
            min_lon, min_lat, max_lon, max_lat = (float(part) for part in value.split(","))
        except ValueError as exc:
            raise serializers.ValidationError("Use minLon,minLat,maxLon,maxLat.") from exc
        if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
            raise serializers.ValidationError("Coordinates are out of range or reversed.")
        if max_lon - min_lon > MAX_BBOX_DEGREES or max_lat - min_lat > MAX_BBOX_DEGREES:
            raise serializers.ValidationError(f"Area is larger than {MAX_BBOX_DEGREES}° per side.")
        return (min_lon, min_lat, max_lon, max_lat)


class GeocodeQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=3, max_length=100, trim_whitespace=True)


# --- Responses ----------------------------------------------------------------
# Plain functions: the output is a direct mapping of service dataclasses, so a tree of
# nested output serializers would add code without adding validation.


def analysis_payload(analysis: Analysis) -> dict:
    return {
        "origin": _place(analysis.origin),
        "destination": _place(analysis.destination),
        "departure_time": analysis.departure.isoformat(),
        "load_lb": analysis.load_lb,
        "interval_mi": analysis.interval_mi,
        "forecast_fetched_at": _iso(analysis.forecast_fetched_at),
        "routes": [
            {
                "id": route.id,
                "label": route.label,
                "geometry": _simplify(route.path.coordinates),
                "is_fallback_alternative": route.path.is_fallback_alternative,
                "metrics": {
                    "distance_mi": round(route.metrics.distance_mi, 1),
                    "duration_s": round(route.metrics.duration_s),
                    "miles_by_risk": {
                        k: round(v, 1) for k, v in route.metrics.miles_by_level.items()
                    },
                    "avg_risk": None
                    if route.metrics.avg_risk is None
                    else round(route.metrics.avg_risk, 2),
                },
                "checkpoints": [_checkpoint(c) for c in route.checkpoints],
            }
            for route in analysis.routes
        ],
        "recommendation": {"route_id": analysis.recommended_route_id, "reason": analysis.reason},
    }


def heatmap_payload(heatmap: Heatmap) -> dict:
    return {
        "points": [list(p) for p in heatmap.points],
        "hours": [h.isoformat() for h in heatmap.hours],
        "scores": heatmap.scores,
    }


def suggestions_payload(suggestions: list[Suggestion]) -> list[dict]:
    return [{"id": s.id, "label": s.label, "position": list(s.position)} for s in suggestions]


def _checkpoint(checkpoint: Checkpoint) -> dict:
    w = checkpoint.weather
    return {
        "index": checkpoint.index,
        "position": [round(checkpoint.position[0], 5), round(checkpoint.position[1], 5)],
        "mile": round(checkpoint.mile, 1),
        "eta": checkpoint.eta.isoformat(),
        "weather": {
            "forecast_time": _iso(w.forecast_time),
            "wind_mph": w.wind_mph,
            "gust_mph": w.gust_mph,
            "rain_in_hr": None if w.rain_in_hr is None else round(w.rain_in_hr, 3),
            "snow_in_hr": None if w.snow_in_hr is None else round(w.snow_in_hr, 2),
        },
        "risk": "UNKNOWN" if checkpoint.level is None else LEVEL_NAMES[checkpoint.level],
        "reasons": checkpoint.reasons,
    }


def _place(place) -> dict:
    return {"label": place.label, "position": list(place.position)}


def _iso(value) -> str | None:
    return None if value is None else value.isoformat()


def _simplify(coordinates: list, min_gap_mi: float = 0.25) -> list[list[float]]:
    """Drop vertices closer than `min_gap_mi` apart; keeps payloads small for long routes."""
    kept = [coordinates[0]]
    for point in coordinates[1:-1]:
        if haversine_mi(kept[-1], point) >= min_gap_mi:
            kept.append(point)
    kept.append(coordinates[-1])
    return [[round(lon, 5), round(lat, 5)] for lon, lat in kept]
