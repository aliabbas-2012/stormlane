from django.db import models


class ForecastCacheEntry(models.Model):
    """Hourly forecast for one rounded location and one UTC day.

    A dedicated table rather than Django's DatabaseCache because a heatmap touches ~750 of
    these at once: here that is one SELECT ... IN and one bulk upsert, where the cache
    backend issues several queries per key."""

    key = models.CharField(max_length=64, primary_key=True)
    payload = models.JSONField()
    expires_at = models.DateTimeField(db_index=True)

    def __str__(self) -> str:
        return self.key
