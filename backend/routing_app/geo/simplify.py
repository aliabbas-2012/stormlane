"""Douglas-Peucker simplification for response geometries. Checkpoints are always computed
on the full geometry; this only shrinks what we send to the browser."""

from .projection import LocalPlane
from .types import LatLon


def douglas_peucker(points: list[LatLon], tolerance_mi: float) -> list[LatLon]:
    if len(points) <= 2:
        return list(points)
    plane = LocalPlane(sum(p[0] for p in points) / len(points))
    xy = [plane.to_xy(p) for p in points]
    xs, ys = [x for x, _ in xy], [y for _, y in xy]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    tol_sq = tolerance_mi**2
    stack = [(0, len(points) - 1)]  # Iterative: routes have 10k+ vertices.
    while stack:
        start, end = stack.pop()
        ax, ay = xs[start], ys[start]
        dx, dy = xs[end] - ax, ys[end] - ay
        seg_sq = dx * dx + dy * dy
        best_i, best_d = -1, tol_sq
        # Inlined point-to-segment distance: this loop dominates analyze() CPU time.
        for i in range(start + 1, end):
            px, py = xs[i] - ax, ys[i] - ay
            if seg_sq == 0:
                d = px * px + py * py
            else:
                t = (px * dx + py * dy) / seg_sq
                t = 0.0 if t < 0 else 1.0 if t > 1 else t
                ex, ey = px - t * dx, py - t * dy
                d = ex * ex + ey * ey
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
