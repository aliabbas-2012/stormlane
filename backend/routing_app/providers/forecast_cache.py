from datetime import UTC, datetime, timedelta
from typing import Any

from asgiref.sync import sync_to_async

from routing_app.models import ForecastCacheEntry


def _load(keys: list[str]) -> dict[str, Any]:
    now = datetime.now(UTC)
    rows = ForecastCacheEntry.objects.filter(key__in=keys, expires_at__gt=now)
    return dict(rows.values_list("key", "payload"))


def _store(entries: dict[str, Any], ttl_s: int) -> None:
    now = datetime.now(UTC)
    expires = now + timedelta(seconds=ttl_s)
    ForecastCacheEntry.objects.bulk_create(
        [ForecastCacheEntry(key=k, payload=v, expires_at=expires) for k, v in entries.items()],
        update_conflicts=True,
        unique_fields=["key"],
        update_fields=["payload", "expires_at"],
    )
    # Housekeeping piggybacks on writes; the expires_at index keeps it cheap.
    ForecastCacheEntry.objects.filter(expires_at__lte=now).delete()


load = sync_to_async(_load)
store = sync_to_async(_store)
