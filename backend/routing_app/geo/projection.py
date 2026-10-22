"""Local equirectangular projection: accurate to well under 1% over a few hundred miles,
which is all the via-point, overlap and simplification maths needs."""

import math

from .distance import EARTH_RADIUS_MI
from .types import LatLon

MI_PER_DEG_LAT = math.pi * EARTH_RADIUS_MI / 180


class LocalPlane:
    def __init__(self, ref_lat: float):
        self.mi_per_deg_lon = MI_PER_DEG_LAT * math.cos(math.radians(ref_lat))

    def to_xy(self, p: LatLon) -> tuple[float, float]:
        return p[1] * self.mi_per_deg_lon, p[0] * MI_PER_DEG_LAT

    def to_latlon(self, x: float, y: float) -> LatLon:
        return y / MI_PER_DEG_LAT, x / self.mi_per_deg_lon
