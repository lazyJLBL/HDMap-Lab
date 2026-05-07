from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from app.geometry_kernel.predicates import (
    EPSILON,
    BBox,
    Orientation,
    bbox_intersects,
    bbox_of_points,
    on_segment,
    orientation,
    same_point,
)
from app.models.point import Coordinate

IntersectionKind = Literal["none", "point", "overlap"]
SegmentRelation = Literal["cross", "touch", "overlap", "disjoint", "endpoint_touch", "collinear_disjoint"]


@dataclass(slots=True)
class SegmentIntersection:
    kind: IntersectionKind
    point: Coordinate | None = None
    overlap: tuple[Coordinate, Coordinate] | None = None
    relation: SegmentRelation = "disjoint"

    @property
    def intersects(self) -> bool:
        return self.kind != "none"


def segments_intersect(
    a1: Coordinate,
    a2: Coordinate,
    b1: Coordinate,
    b2: Coordinate,
    eps: float | None = None,
) -> bool:
    return segment_intersection(a1, a2, b1, b2, eps).intersects


def segment_intersection(
    a1: Coordinate,
    a2: Coordinate,
    b1: Coordinate,
    b2: Coordinate,
    eps: float | None = None,
) -> SegmentIntersection:
    return classify_segment_intersection(a1, a2, b1, b2, eps)


def line_segment_relation(
    a1: Coordinate,
    a2: Coordinate,
    b1: Coordinate,
    b2: Coordinate,
    eps: float | None = None,
) -> SegmentRelation:
    return classify_segment_intersection(a1, a2, b1, b2, eps).relation


def classify_segment_intersection(
    a1: Coordinate,
    a2: Coordinate,
    b1: Coordinate,
    b2: Coordinate,
    eps: float | None = None,
) -> SegmentIntersection:
    if not bbox_intersects(_segment_bbox(a1, a2), _segment_bbox(b1, b2), eps):
        if _all_collinear(a1, a2, b1, b2, eps):
            return SegmentIntersection("none", relation="collinear_disjoint")
        return SegmentIntersection("none", relation="disjoint")

    a_degenerate = same_point(a1, a2, eps)
    b_degenerate = same_point(b1, b2, eps)
    if a_degenerate and b_degenerate:
        if same_point(a1, b1, eps):
            return SegmentIntersection("point", point=a1, relation="endpoint_touch")
        return SegmentIntersection("none", relation="disjoint")
    if a_degenerate:
        if on_segment(a1, b1, b2, eps):
            relation: SegmentRelation = "endpoint_touch" if _is_endpoint(a1, b1, b2, eps) else "touch"
            return SegmentIntersection("point", point=a1, relation=relation)
        return SegmentIntersection("none", relation="disjoint")
    if b_degenerate:
        if on_segment(b1, a1, a2, eps):
            relation = "endpoint_touch" if _is_endpoint(b1, a1, a2, eps) else "touch"
            return SegmentIntersection("point", point=b1, relation=relation)
        return SegmentIntersection("none", relation="disjoint")

    o1 = orientation(a1, a2, b1, eps)
    o2 = orientation(a1, a2, b2, eps)
    o3 = orientation(b1, b2, a1, eps)
    o4 = orientation(b1, b2, a2, eps)

    if o1 == o2 == o3 == o4 == Orientation.COLLINEAR:
        overlap = overlapping_segment(a1, a2, b1, b2, eps)
        if overlap is None:
            return SegmentIntersection("none", relation="collinear_disjoint")
        start, end = overlap
        if same_point(start, end, eps):
            return SegmentIntersection("point", point=start, relation="endpoint_touch")
        return SegmentIntersection("overlap", overlap=overlap, relation="overlap")

    endpoint = _shared_endpoint(a1, a2, b1, b2, eps)
    if endpoint is not None:
        return SegmentIntersection("point", point=endpoint, relation="endpoint_touch")

    touches = _collinear_endpoint_touches(a1, a2, b1, b2, eps)
    if touches is not None:
        relation = "endpoint_touch" if _is_original_endpoint_touch(touches, a1, a2, b1, b2, eps) else "touch"
        return SegmentIntersection("point", point=touches, relation=relation)

    if o1 != o2 and o3 != o4:
        point = intersection_point(a1, a2, b1, b2, eps)
        if point is None:
            return SegmentIntersection("none", relation="disjoint")
        return SegmentIntersection("point", point=point, relation="cross")

    return SegmentIntersection("none", relation="disjoint")


def intersection_point(
    a1: Coordinate,
    a2: Coordinate,
    b1: Coordinate,
    b2: Coordinate,
    eps: float | None = None,
) -> Coordinate | None:
    """Return the infinite-line intersection point, or ``None`` if parallel."""

    x1, y1 = a1
    x2, y2 = a2
    x3, y3 = b1
    x4, y4 = b2
    denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    scale = max(abs(x2 - x1), abs(y2 - y1), abs(x4 - x3), abs(y4 - y3), 1.0)
    tolerance = (EPSILON if eps is None else abs(eps)) * scale * scale
    if abs(denominator) <= tolerance:
        return None
    det_a = x1 * y2 - y1 * x2
    det_b = x3 * y4 - y3 * x4
    px = (det_a * (x3 - x4) - (x1 - x2) * det_b) / denominator
    py = (det_a * (y3 - y4) - (y1 - y2) * det_b) / denominator
    return (px, py)


def overlapping_segment(
    a1: Coordinate,
    a2: Coordinate,
    b1: Coordinate,
    b2: Coordinate,
    eps: float | None = None,
) -> tuple[Coordinate, Coordinate] | None:
    if not _all_collinear(a1, a2, b1, b2, eps):
        return None
    if same_point(a1, a2, eps):
        return (a1, a1) if on_segment(a1, b1, b2, eps) else None
    if same_point(b1, b2, eps):
        return (b1, b1) if on_segment(b1, a1, a2, eps) else None

    axis = 0 if abs(a2[0] - a1[0]) >= abs(a2[1] - a1[1]) else 1
    a_min, a_max = sorted((a1, a2), key=lambda point: (point[axis], point[1 - axis]))
    b_min, b_max = sorted((b1, b2), key=lambda point: (point[axis], point[1 - axis]))
    start = max(a_min, b_min, key=lambda point: (point[axis], point[1 - axis]))
    end = min(a_max, b_max, key=lambda point: (point[axis], point[1 - axis]))
    if _lex_less(end, start, axis, eps):
        return None
    if on_segment(start, a1, a2, eps) and on_segment(start, b1, b2, eps) and on_segment(end, a1, a2, eps) and on_segment(end, b1, b2, eps):
        return start, end
    return None


def _segment_bbox(start: Coordinate, end: Coordinate) -> BBox:
    return bbox_of_points((start, end))


def _all_collinear(a1: Coordinate, a2: Coordinate, b1: Coordinate, b2: Coordinate, eps: float | None) -> bool:
    if same_point(a1, a2, eps):
        return orientation(b1, b2, a1, eps) == Orientation.COLLINEAR
    return orientation(a1, a2, b1, eps) == Orientation.COLLINEAR and orientation(a1, a2, b2, eps) == Orientation.COLLINEAR


def _shared_endpoint(
    a1: Coordinate,
    a2: Coordinate,
    b1: Coordinate,
    b2: Coordinate,
    eps: float | None,
) -> Coordinate | None:
    for first in (a1, a2):
        for second in (b1, b2):
            if same_point(first, second, eps):
                return first
    return None


def _collinear_endpoint_touches(
    a1: Coordinate,
    a2: Coordinate,
    b1: Coordinate,
    b2: Coordinate,
    eps: float | None,
) -> Coordinate | None:
    for point, start, end in ((b1, a1, a2), (b2, a1, a2), (a1, b1, b2), (a2, b1, b2)):
        if on_segment(point, start, end, eps):
            return point
    return None


def _is_endpoint(point: Coordinate, start: Coordinate, end: Coordinate, eps: float | None) -> bool:
    return same_point(point, start, eps) or same_point(point, end, eps)


def _is_original_endpoint_touch(
    point: Coordinate,
    a1: Coordinate,
    a2: Coordinate,
    b1: Coordinate,
    b2: Coordinate,
    eps: float | None,
) -> bool:
    return _is_endpoint(point, a1, a2, eps) and _is_endpoint(point, b1, b2, eps)


def _lex_less(a: Coordinate, b: Coordinate, axis: int, eps: float | None) -> bool:
    tolerance = EPSILON if eps is None else abs(eps)
    if a[axis] < b[axis] - tolerance:
        return True
    if math.isclose(a[axis], b[axis], abs_tol=tolerance):
        return a[1 - axis] < b[1 - axis] - tolerance
    return False
