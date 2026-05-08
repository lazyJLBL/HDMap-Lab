from __future__ import annotations

import math
import sys
from decimal import Decimal, localcontext
from enum import IntEnum
from typing import Iterable

from app.models.point import Coordinate

EPSILON = 1e-12
MACHINE_EPSILON = sys.float_info.epsilon
BBox = tuple[float, float, float, float]


class Orientation(IntEnum):
    CLOCKWISE = -1
    COLLINEAR = 0
    COUNTER_CLOCKWISE = 1


def orientation_value(a: Coordinate, b: Coordinate, c: Coordinate) -> float:
    """Return the signed twice-area determinant for triangle ``abc``.

    The determinant is evaluated after translating all points by ``a``. This
    reduces cancellation when coordinates are large but local deltas are small.
    """

    abx = float(b[0]) - float(a[0])
    aby = float(b[1]) - float(a[1])
    acx = float(c[0]) - float(a[0])
    acy = float(c[1]) - float(a[1])
    return math.fsum((abx * acy, -(aby * acx)))


def orientation(a: Coordinate, b: Coordinate, c: Coordinate, eps: float | None = None) -> Orientation:
    """Classify the orientation of three points with scale-aware tolerance.

    ``eps=None`` uses a floating-point error bound based on the determinant
    products. Passing ``eps`` keeps compatibility with older callers while still
    scaling the tolerance by the local coordinate span.
    """

    value = orientation_value(a, b, c)
    tolerance = _orientation_tolerance(a, b, c, eps)
    if abs(value) <= tolerance:
        return robust_orientation(a, b, c, tolerance=tolerance)
    return Orientation.COUNTER_CLOCKWISE if value > 0.0 else Orientation.CLOCKWISE


def robust_orientation(a: Coordinate, b: Coordinate, c: Coordinate, tolerance: float | None = None) -> Orientation:
    """Return a robust orientation for near-collinear triples.

    The fast path uses the translated double-precision determinant. Ambiguous
    cases are recomputed with ``Decimal`` from the input values' string
    representation. This is not a full exact-arithmetic predicate, but it is
    substantially more stable than a single fixed epsilon for map coordinates.
    """

    value = orientation_value(a, b, c)
    bound = _orientation_tolerance(a, b, c, None) if tolerance is None else tolerance
    if abs(value) > bound:
        return Orientation.COUNTER_CLOCKWISE if value > 0.0 else Orientation.CLOCKWISE

    return exact_orientation_fallback(a, b, c, tolerance=bound)


def exact_orientation_fallback(
    a: Coordinate,
    b: Coordinate,
    c: Coordinate,
    tolerance: float | Decimal = 0.0,
) -> Orientation:
    """Recompute orientation with high-precision ``Decimal`` arithmetic.

    This fallback is intentionally reserved for ambiguous triples. It converts
    the input values through ``str(value)`` so common lon/lat decimals are
    preserved better than a repeated binary-float determinant. It is still not
    symbolic exact arithmetic if precision was already lost before the value
    reached this function.
    """

    det = _decimal_orientation_value(a, b, c)
    decimal_bound = Decimal(str(tolerance))
    if abs(det) <= decimal_bound:
        return Orientation.COLLINEAR
    return Orientation.COUNTER_CLOCKWISE if det > 0 else Orientation.CLOCKWISE


def signed_area_ring(points: list[Coordinate]) -> float:
    """Return signed polygon ring area; CCW rings are positive."""

    if len(points) < 3:
        return 0.0
    area2 = 0.0
    ring = points if is_ring_closed(points) else [*points, points[0]]
    for start, end in zip(ring, ring[1:], strict=False):
        area2 = math.fsum((area2, float(start[0]) * float(end[1]), -(float(end[0]) * float(start[1]))))
    return area2 / 2.0


def is_collinear(a: Coordinate, b: Coordinate, c: Coordinate, eps: float | None = None) -> bool:
    return orientation(a, b, c, eps) == Orientation.COLLINEAR


def on_segment(point: Coordinate, start: Coordinate, end: Coordinate, eps: float | None = None) -> bool:
    if orientation(start, end, point, eps) != Orientation.COLLINEAR:
        return False
    tolerance = _point_tolerance(start, end, point, eps=eps)
    return (
        min(start[0], end[0]) - tolerance <= point[0] <= max(start[0], end[0]) + tolerance
        and min(start[1], end[1]) - tolerance <= point[1] <= max(start[1], end[1]) + tolerance
    )


def same_point(a: Coordinate, b: Coordinate, eps: float | None = None) -> bool:
    tolerance = _point_tolerance(a, b, eps=eps)
    return abs(float(a[0]) - float(b[0])) <= tolerance and abs(float(a[1]) - float(b[1])) <= tolerance


def bbox_of_points(points: Iterable[Coordinate]) -> BBox:
    coords = list(points)
    if not coords:
        raise ValueError("bbox_of_points requires at least one point")
    xs = [float(point[0]) for point in coords]
    ys = [float(point[1]) for point in coords]
    return min(xs), min(ys), max(xs), max(ys)


def bbox_intersects(a: BBox, b: BBox, eps: float | None = None) -> bool:
    tolerance = _bbox_tolerance(a, b, eps)
    return not (
        a[2] < b[0] - tolerance
        or b[2] < a[0] - tolerance
        or a[3] < b[1] - tolerance
        or b[3] < a[1] - tolerance
    )


def bbox_contains_point(bbox: BBox, point: Coordinate, eps: float | None = None) -> bool:
    tolerance = _bbox_tolerance(bbox, (point[0], point[1], point[0], point[1]), eps)
    return (
        bbox[0] - tolerance <= point[0] <= bbox[2] + tolerance
        and bbox[1] - tolerance <= point[1] <= bbox[3] + tolerance
    )


def is_ring_closed(points: list[Coordinate], eps: float | None = None) -> bool:
    return len(points) > 1 and same_point(points[0], points[-1], eps)


def _orientation_tolerance(a: Coordinate, b: Coordinate, c: Coordinate, eps: float | None) -> float:
    abx = float(b[0]) - float(a[0])
    aby = float(b[1]) - float(a[1])
    acx = float(c[0]) - float(a[0])
    acy = float(c[1]) - float(a[1])
    scale = max(abs(abx), abs(aby), abs(acx), abs(acy), 1.0)
    if eps is not None:
        return abs(eps) * scale * scale
    product_sum = abs(abx * acy) + abs(aby * acx)
    return max(64.0 * MACHINE_EPSILON * product_sum, 8.0 * MACHINE_EPSILON * scale * scale)


def _decimal_orientation_value(a: Coordinate, b: Coordinate, c: Coordinate) -> Decimal:
    with localcontext() as context:
        context.prec = 80
        ax, ay = Decimal(str(a[0])), Decimal(str(a[1]))
        bx, by = Decimal(str(b[0])), Decimal(str(b[1]))
        cx, cy = Decimal(str(c[0])), Decimal(str(c[1]))
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _point_tolerance(*points: Coordinate, eps: float | None = None) -> float:
    scale = max((abs(float(value)) for point in points for value in point), default=1.0)
    scale = max(scale, 1.0)
    if eps is not None:
        return abs(eps) * scale
    return max(EPSILON, 16.0 * MACHINE_EPSILON * scale)


def _bbox_tolerance(a: BBox, b: BBox, eps: float | None) -> float:
    scale = max((abs(float(value)) for value in (*a, *b)), default=1.0)
    scale = max(scale, 1.0)
    if eps is not None:
        return abs(eps) * scale
    return max(EPSILON, 16.0 * MACHINE_EPSILON * scale)
