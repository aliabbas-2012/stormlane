from bisect import bisect_right

from .types import LatLon


def _locate(cum: list[float], x: float) -> tuple[int, float]:
    """Index i and fraction t such that x lies t of the way from cum[i] to cum[i+1]."""
    if x <= cum[0]:
        return 0, 0.0
    if x >= cum[-1]:
        return len(cum) - 2, 1.0
    i = bisect_right(cum, x) - 1
    span = cum[i + 1] - cum[i]
    return i, (x - cum[i]) / span if span > 0 else 0.0


def point_at_mile(points: list[LatLon], cum_miles: list[float], mile: float) -> LatLon:
    """Position along the polyline at `mile`, clamped to the route ends.

    Linear lat/lon interpolation is accurate here because route vertices are close together.
    """
    if len(points) == 1:
        return points[0]
    i, t = _locate(cum_miles, mile)
    (lat1, lon1), (lat2, lon2) = points[i], points[i + 1]
    return (lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t)


def value_at_mile(cum_miles: list[float], values: list[float], mile: float) -> float:
    """Linearly interpolate a per-vertex series (e.g. elapsed seconds) at `mile`."""
    if len(values) == 1:
        return values[0]
    i, t = _locate(cum_miles, mile)
    return values[i] + (values[i + 1] - values[i]) * t
