"""Every error response uses the same shape: {"error": {"code", "message"}}."""

import logging
from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from routing_app.providers.http import ProviderError
from routing_app.services.errors import ServiceError

logger = logging.getLogger(__name__)

# Upstream failures are not the client's fault, except "no route", which is about the input.
_PROVIDER_STATUS = {
    "no_route": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "rate_limited": status.HTTP_503_SERVICE_UNAVAILABLE,
    "unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
}


def _flatten(detail: Any) -> str:
    if isinstance(detail, dict):
        return "; ".join(
            _flatten(v) if k == "non_field_errors" else f"{k}: {_flatten(v)}"
            for k, v in detail.items()
        )
    if isinstance(detail, list):
        return "; ".join(_flatten(v) for v in detail)
    return str(detail)


def _error(code: str, message: str, http_status: int) -> Response:
    return Response({"error": {"code": code, "message": message}}, status=http_status)


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, ServiceError):
        return _error(exc.code, exc.message, exc.http_status)
    if isinstance(exc, ProviderError):
        logger.warning("provider error: %s", exc)
        http_status = _PROVIDER_STATUS.get(exc.code, status.HTTP_502_BAD_GATEWAY)
        message = (
            exc.message
            if exc.code == "no_route"
            else (f"Upstream service ({exc.provider}) failed. Please try again shortly.")
        )
        return _error(f"upstream_{exc.code}", message, http_status)

    response = drf_exception_handler(exc, context)
    if response is None:
        return None  # Unhandled -> Django's 500
    code = (
        "validation_error"
        if isinstance(exc, ValidationError)
        else getattr(exc, "default_code", "error")
    )
    detail = exc.detail if isinstance(exc, APIException) else response.data
    return _error(code, _flatten(detail), response.status_code)
