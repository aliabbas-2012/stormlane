"""Shared outbound-HTTP policy: timeouts, one retry with backoff, uniform errors."""

import asyncio
import logging
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
RETRY_BACKOFF_S = 0.5
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ProviderError(Exception):
    """An external provider failed or returned something unusable."""

    def __init__(self, provider: str, code: str, message: str):
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.code = code
        self.message = message


def make_client() -> httpx.AsyncClient:
    # One client per orchestrated request: async_to_sync runs each request on its own event
    # loop, and an AsyncClient must not outlive the loop that created it.
    return httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": settings.HTTP_USER_AGENT},
        follow_redirects=True,
    )


async def get_json(client: httpx.AsyncClient, provider: str, url: str, params: Any = None) -> Any:
    """GET and decode JSON, retrying once on network errors, 429 and 5xx."""
    for attempt in (1, 2):
        try:
            response = await client.get(url, params=params)
        except httpx.TransportError as exc:
            if attempt == 2:
                raise ProviderError(provider, "unavailable", f"request failed: {exc!r}") from exc
            logger.warning("%s transport error, retrying: %r", provider, exc)
        else:
            if response.status_code in _RETRYABLE_STATUS and attempt == 1:
                logger.warning("%s HTTP %s, retrying", provider, response.status_code)
            elif response.status_code == 429:
                raise ProviderError(provider, "rate_limited", "rate limit exceeded")
            elif response.status_code >= 400:
                raise ProviderError(
                    provider,
                    "bad_response",
                    f"HTTP {response.status_code}: {response.text[:200]}",
                )
            else:
                try:
                    return response.json()
                except ValueError as exc:
                    raise ProviderError(provider, "bad_response", "invalid JSON") from exc
        await asyncio.sleep(RETRY_BACKOFF_S)
    raise AssertionError("unreachable")
