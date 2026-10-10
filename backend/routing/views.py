"""HTTP layer: validate input, delegate to services, shape the response.

Views stay thin; business rules live in routing.services.
"""

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from routing import serializers
from routing.services import analysis, heatmap, here


class HealthView(APIView):
    """Liveness probe for the hosting platform."""

    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


class AnalyzeView(APIView):
    throttle_scope = "analyze"

    def post(self, request: Request) -> Response:
        params = serializers.AnalyzeRequestSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        result = analysis.analyze(
            data["origin"],
            data["destination"],
            data["departure_time"],
            data["load_lb"],
            data["interval_mi"],
        )
        return Response(serializers.analysis_payload(result))


class HeatmapView(APIView):
    throttle_scope = "heatmap"

    def get(self, request: Request) -> Response:
        params = serializers.HeatmapQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        result = heatmap.corridor_heatmap(data["bbox"], data["start"], data["load_lb"])
        return Response(serializers.heatmap_payload(result))


class GeocodeView(APIView):
    throttle_scope = "geocode"

    def get(self, request: Request) -> Response:
        params = serializers.GeocodeQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        return Response(serializers.suggestions_payload(here.suggest(params.validated_data["q"])))
