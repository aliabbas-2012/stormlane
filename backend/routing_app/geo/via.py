from .projection import LocalPlane
from .types import LatLon

# Offsets as a fraction of the straight-line distance, in the order they are tried:
# small detours on both sides first, wider ones only if needed.
VIA_OFFSET_ROUNDS: tuple[tuple[float, ...], ...] = ((0.15, -0.15), (0.30, -0.30))


def perpendicular_via_point(origin: LatLon, destination: LatLon, fraction: float) -> LatLon:
    """Point offset from the origin->destination midpoint, perpendicular to that line, by
    `fraction` of the straight-line distance. Positive = left of the direction of travel."""
    plane = LocalPlane((origin[0] + destination[0]) / 2)
    ox, oy = plane.to_xy(origin)
    dx, dy = plane.to_xy(destination)
    mx, my = (ox + dx) / 2, (oy + dy) / 2
    vx, vy = dx - ox, dy - oy  # Length = straight-line distance, so no normalising needed.
    return plane.to_latlon(mx - vy * fraction, my + vx * fraction)
