"""Every error response uses the same shape: {"error": {"code", "message"}}."""

from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class ApiError(APIException):
    """Raise from views/services for a domain error with a specific code."""

    def __init__(self, code: str, message: str, http_status: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(detail=message, code=code)
        self.status_code = http_status
        self.error_code = code


def _flatten(detail: Any) -> str:
    if isinstance(detail, dict):
        return "; ".join(f"{k}: {_flatten(v)}" for k, v in detail.items())
    if isinstance(detail, list):
        return "; ".join(_flatten(v) for v in detail)
    return str(detail)


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = drf_exception_handler(exc, context)
    if response is None:
        return None  # Unhandled -> Django's 500
    if isinstance(exc, ApiError):
        code = exc.error_code
    elif isinstance(exc, ValidationError):
        code = "validation_error"
    else:
        code = getattr(exc, "default_code", "error")
    detail = exc.detail if isinstance(exc, APIException) else response.data
    response.data = {"error": {"code": code, "message": _flatten(detail)}}
    return response
