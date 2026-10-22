import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from asgiref.sync import sync_to_async
from django.db import connections

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


@pytest.fixture(scope="session", autouse=True)
def _close_worker_thread_connections(
    django_db_setup: Any, django_db_blocker: Any
) -> Iterator[None]:
    yield
    # Tests drive async code with asyncio.run, so ORM calls run on asgiref's shared worker
    # thread and leave a connection open there that would block test-DB teardown.
    with django_db_blocker.unblock():
        asyncio.run(sync_to_async(connections.close_all)())
