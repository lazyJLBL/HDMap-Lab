from __future__ import annotations

from enum import IntEnum

from app.models.point import Coordinate

EPSILON = 1e-12


class Orientation(IntEnum):
    CLOCKWISE = -1
    COLLINEAR = 0
    COUNTER_CLOCKWISE = 1


def orientation_value(a: Coordinate, b: Coordinate, c: Coordinate) -> float:
    """Signed twice-area of triangle abc in planar lon/lat coordinates."""

    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def orientation(a: Coordinate, b: Coordinate, c: Coordinate, eps: float = EPSILON) -> Orientation:
    value = orientation_value(a, b, c)
    scale = max(
        abs(b[0] - a[0]),
        abs(b[1] - a[1]),
        abs(c[0] - a[0]),
        abs(c[1] - a[1]),
        1.0,
    )
    tolerance = eps * scale * scale
    if abs(value) <= tolerance:
        return Orientation.COLLINEAR
    return Orientation.COUNTER_CLOCKWISE if value > 0 else Orientation.CLOCKWISE


def on_segment(point: Coordinate, start: Coordinate, end: Coordinate, eps: float = EPSILON) -> bool:
    if orientation(start, end, point, eps) != Orientation.COLLINEAR:
        return False
    return (
        min(start[0], end[0]) - eps <= point[0] <= max(start[0], end[0]) + eps
        and min(start[1], end[1]) - eps <= point[1] <= max(start[1], end[1]) + eps
    )


def same_point(a: Coordinate, b: Coordinate, eps: float = EPSILON) -> bool:
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps
