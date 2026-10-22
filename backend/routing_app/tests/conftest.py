from typing import Any

import pytest

from routing_app.providers import http


@pytest.fixture(autouse=True)
def _isolated_cache(settings: Any) -> None:
    # Unit tests must not need Postgres or see each other's cached provider responses.
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.TOMTOM_API_KEY = ""
    from django.core.cache import cache

    cache.clear()


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(http, "RETRY_BACKOFF_S", 0)
