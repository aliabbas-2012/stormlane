from asgiref.sync import async_to_sync
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from routing_app.providers.geocoding import geocode
from routing_app.providers.http import make_client
from routing_app.services.analyze import AnalyzeParams, analyze
from routing_app.services.heatmap import build_heatmap

from .serializers import AnalyzeRequestSerializer, GeocodeQuerySerializer, HeatmapRequestSerializer


class HealthView(APIView):
    """Cheap liveness probe; the frontend pings it on load to wake a sleeping backend."""

    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


async def _geocode(query: str) -> list[dict[str, object]]:
    async with make_client() as client:
        return [
            {"label": p.label, "lat": p.lat, "lon": p.lon} for p in await geocode(client, query)
        ]


class GeocodeView(APIView):
    def get(self, request: Request) -> Response:
        params = GeocodeQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        return Response(async_to_sync(_geocode)(params.validated_data["q"]))


class AnalyzeView(APIView):
    def post(self, request: Request) -> Response:
        body = AnalyzeRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        params = AnalyzeParams(
            origin=(data["origin"]["lat"], data["origin"]["lon"]),
            destination=(data["destination"]["lat"], data["destination"]["lon"]),
            origin_label=data["origin"]["label"],
            destination_label=data["destination"]["label"],
            departure=data["departure_time"],
            load_lbs=data["load_lbs"],
            interval_miles=int(data["interval_miles"]),
        )
        # Sync DRF view; the service fans out to external APIs concurrently on its own loop.
        return Response(async_to_sync(analyze)(params))


class HeatmapView(APIView):
    def post(self, request: Request) -> Response:
        body = HeatmapRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(async_to_sync(build_heatmap)(body.validated_data["analysis_id"]))
