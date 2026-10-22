import math
from itertools import accumulate, pairwise

from .types import LatLon

EARTH_RADIUS_MI = 3958.7613


def haversine_mi(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(min(h, 1.0)))


def cumulative_miles(points: list[LatLon]) -> list[float]:
    """Distance from the first point to each vertex; same length as `points`."""
    return list(accumulate((haversine_mi(a, b) for a, b in pairwise(points)), initial=0.0))
