"""Elapsed-time series along a route, and mapping ETAs onto forecast hours."""

from datetime import datetime, timedelta
from itertools import accumulate


def cumulative_seconds_from_segments(segment_durations_s: list[float]) -> list[float]:
    """Per-vertex elapsed time from per-segment durations (e.g. OSRM annotations.duration)."""
    return list(accumulate(segment_durations_s, initial=0.0))


def proportional_cumulative_seconds(cum_miles: list[float], total_s: float) -> list[float]:
    """Fallback when the provider gives no per-segment timing: assume constant average speed."""
    total_mi = cum_miles[-1]
    if total_mi <= 0:
        return [0.0 for _ in cum_miles]
    return [total_s * m / total_mi for m in cum_miles]


def floor_to_hour(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


def forecast_hours_for_eta(eta: datetime) -> tuple[datetime, datetime]:
    """(instantaneous_hour, accumulation_hour) to read from an hourly forecast.

    Wind is an instantaneous value, so we read the hour containing the ETA (floor).
    Open-Meteo precipitation at timestamp T is the total over the *preceding* hour (T-1h, T],
    so the hour containing the ETA, [floor, floor+1h), is stored at floor + 1h.
    """
    hour = floor_to_hour(eta)
    return hour, hour + timedelta(hours=1)
