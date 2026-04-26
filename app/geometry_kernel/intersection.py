from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.geometry_kernel.predicates import EPSILON, Orientation, on_segment, orientation, same_point
from app.models.point import Coordinate

IntersectionKind = Literal["none", "point", "overlap"]


@dataclass(slots=True)
class SegmentIntersection:
    kind: IntersectionKind
    point: Coordinate | None = None
    overlap: tuple[Coordinate, Coordinate] | None = None

    @property
    def intersects(self) -> bool:
        return self.kind != "none"


def segments_intersect(a1: Coordinate, a2: Coordinate, b1: Coordinate, b2: Coordinate, eps: float = EPSILON) -> bool:
    return segment_intersection(a1, a2, b1, b2, eps).intersects


def segment_intersection(
    a1: Coordinate,
    a2: Coordinate,
    b1: Coordinate,
    b2: Coordinate,
    eps: float = EPSILON,
) -> SegmentIntersection:
    o1 = orientation(a1, a2, b1, eps)
    o2 = orientation(a1, a2, b2, eps)
    o3 = orientation(b1, b2, a1, eps)
    o4 = orientation(b1, b2, a2, eps)

    if o1 != o2 and o3 != o4:
        return SegmentIntersection("point", _line_intersection(a1, a2, b1, b2))

    endpoint = _shared_endpoint(a1, a2, b1, b2, eps)
    if endpoint is not None:
        return SegmentIntersection("point", endpoint)

    if o1 == Orientation.COLLINEAR and o2 == Orientation.COLLINEAR and o3 == Orientation.COLLINEAR and o4 == Orientation.COLLINEAR:
        overlap = _collinear_overlap(a1, a2, b1, b2, eps)
        if overlap is None:
            return SegmentIntersection("none")
        start, end = overlap
        if same_point(start, end, eps):
            return SegmentIntersection("point", start)
        return SegmentIntersection("overlap", overlap=overlap)

    for point, start, end in ((b1, a1, a2), (b2, a1, a2), (a1, b1, b2), (a2, b1, b2)):
        if on_segment(point, start, end, eps):
            return SegmentIntersection("point", point)

    return SegmentIntersection("none")


def _shared_endpoint(a1: Coordinate, a2: Coordinate, b1: Coordinate, b2: Coordinate, eps: float) -> Coordinate | None:
    for first in (a1, a2):
        for second in (b1, b2):
            if same_point(first, second, eps):
                return first
    return None


def _line_intersection(a1: Coordinate, a2: Coordinate, b1: Coordinate, b2: Coordinate) -> Coordinate:
    x1, y1 = a1
    x2, y2 = a2
    x3, y3 = b1
    x4, y4 = b2
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) <= EPSILON:
        return a1
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
    return px, py


def _collinear_overlap(
    a1: Coordinate,
    a2: Coordinate,
    b1: Coordinate,
    b2: Coordinate,
    eps: float,
) -> tuple[Coordinate, Coordinate] | None:
    axis = 0 if abs(a2[0] - a1[0]) >= abs(a2[1] - a1[1]) else 1
    points = sorted([a1, a2, b1, b2], key=lambda point: (point[axis], point[1 - axis]))
    start, end = points[1], points[2]
    if on_segment(start, a1, a2, eps) and on_segment(start, b1, b2, eps) and on_segment(end, a1, a2, eps) and on_segment(end, b1, b2, eps):
        return start, end
    return None
