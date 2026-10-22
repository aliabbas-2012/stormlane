"""Douglas-Peucker simplification for response geometries. Checkpoints are always computed
on the full geometry; this only shrinks what we send to the browser."""

from .projection import LocalPlane
from .types import LatLon


def _perpendicular_sq(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    seg_sq = dx * dx + dy * dy
    if seg_sq == 0:
        return (px - ax) ** 2 + (py - ay) ** 2
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_sq))
    cx, cy = ax + t * dx, ay + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2


def douglas_peucker(points: list[LatLon], tolerance_mi: float) -> list[LatLon]:
    if len(points) <= 2:
        return list(points)
    plane = LocalPlane(sum(p[0] for p in points) / len(points))
    xy = [plane.to_xy(p) for p in points]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    tol_sq = tolerance_mi**2
    stack = [(0, len(points) - 1)]  # Iterative: routes have 10k+ vertices.
    while stack:
        start, end = stack.pop()
        best_i, best_d = -1, tol_sq
        for i in range(start + 1, end):
            d = _perpendicular_sq(xy[i], xy[start], xy[end])
            if d > best_d:
                best_i, best_d = i, d
        if best_i != -1:
            keep[best_i] = True
            stack.extend(((start, best_i), (best_i, end)))
    return [p for p, k in zip(points, keep, strict=True) if k]


def simplify_to_max_points(
    points: list[LatLon], max_points: int, initial_tolerance_mi: float = 0.01
) -> list[LatLon]:
    """Smallest doubling tolerance that brings the geometry under `max_points`."""
    tolerance = initial_tolerance_mi
    simplified = douglas_peucker(points, tolerance)
    while len(simplified) > max_points:
        tolerance *= 2
        simplified = douglas_peucker(points, tolerance)
    return simplified
