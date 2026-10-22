from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Cheap liveness probe; the frontend pings it on load to wake a sleeping backend."""

    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})
