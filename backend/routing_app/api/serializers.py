from datetime import datetime
from typing import Any

from rest_framework import serializers

from routing_app.geo import haversine_mi

MAX_LOAD_LBS = 200_000  # Above the 80,000 lb legal gross we warn rather than reject (permits).


class LocationSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)
    label = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class AwareDateTimeField(serializers.Field):
    """ISO 8601 with an explicit offset. A naive time is ambiguous (whose local time?), so it is
    rejected rather than silently interpreted as server time."""

    default_error_messages = {
        "invalid": "Must be an ISO 8601 datetime, e.g. 2026-10-23T14:00:00-05:00.",
        "naive": "Must include a UTC offset or 'Z', e.g. 2026-10-23T14:00:00-05:00.",
    }

    def to_internal_value(self, data: Any) -> datetime:
        if not isinstance(data, str):
            self.fail("invalid")
        try:
            value = datetime.fromisoformat(data)
        except ValueError:
            self.fail("invalid")
        if value.tzinfo is None or value.utcoffset() is None:
            self.fail("naive")
        return value

    def to_representation(self, value: datetime) -> str:
        return value.isoformat()


class AnalyzeRequestSerializer(serializers.Serializer):
    origin = LocationSerializer()
    destination = LocationSerializer()
    departure_time = AwareDateTimeField()
    load_lbs = serializers.FloatField(min_value=1, max_value=MAX_LOAD_LBS)
    interval_miles = serializers.ChoiceField(choices=[10, 25, 50])

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        o, d = attrs["origin"], attrs["destination"]
        if haversine_mi((o["lat"], o["lon"]), (d["lat"], d["lon"])) < 1:
            raise serializers.ValidationError(
                "Origin and destination must be at least 1 mile apart."
            )
        return attrs


class GeocodeQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=2, max_length=200, trim_whitespace=True)


class HeatmapRequestSerializer(serializers.Serializer):
    analysis_id = serializers.RegexField(r"^[0-9a-f]{32}$")
