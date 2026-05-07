from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.geometry_kernel.intersection import SegmentIntersection, segment_intersection
from app.geometry_kernel.predicates import EPSILON, bbox_of_points, on_segment, same_point, signed_area_ring
from app.models.point import Coordinate

PointLocation = Literal["inside", "outside", "boundary"]
BoundaryPolicy = Literal["inside", "outside", "boundary"]
RingOrientation = Literal["ccw", "cw", "degenerate"]


@dataclass(slots=True)
class RingSelfIntersection:
    first_segment_index: int
    second_segment_index: int
    intersection: SegmentIntersection

    def to_dict(self) -> dict[str, object]:
        return {
            "first_segment_index": self.first_segment_index,
            "second_segment_index": self.second_segment_index,
            "kind": self.intersection.kind,
            "relation": self.intersection.relation,
            "point": list(self.intersection.point) if self.intersection.point else None,
            "overlap": [list(point) for point in self.intersection.overlap] if self.intersection.overlap else None,
        }


def point_in_ring(
    point: Coordinate,
    ring: list[Coordinate],
    boundary_policy: BoundaryPolicy = "boundary",
) -> PointLocation:
    location = _point_in_ring_raw(point, close_ring(ring))
    return _apply_boundary_policy(location, boundary_policy)


def point_in_polygon(
    point: Coordinate,
    polygon: list[list[Coordinate]],
    boundary_policy: BoundaryPolicy = "boundary",
) -> PointLocation:
    if not polygon or not polygon[0]:
        return "outside"

    outer = _point_in_ring_raw(point, close_ring(polygon[0]))
    if outer == "boundary":
        return _apply_boundary_policy("boundary", boundary_policy)
    if outer == "outside":
        return "outside"

    for hole in polygon[1:]:
        hole_location = _point_in_ring_raw(point, close_ring(hole))
        if hole_location == "boundary":
            return _apply_boundary_policy("boundary", boundary_policy)
        if hole_location == "inside":
            return "outside"
    return "inside"


def point_in_multipolygon(
    point: Coordinate,
    multipolygon: list[list[list[Coordinate]]],
    boundary_policy: BoundaryPolicy = "boundary",
) -> PointLocation:
    saw_boundary = False
    for polygon in multipolygon:
        location = point_in_polygon(point, polygon, "boundary")
        if location == "inside":
            return "inside"
        if location == "boundary":
            saw_boundary = True
    if saw_boundary:
        return _apply_boundary_policy("boundary", boundary_policy)
    return "outside"


def polygon_area(polygon_or_ring: list[Coordinate] | list[list[Coordinate]]) -> float:
    """Return positive area for a ring or polygon-with-holes."""

    if not polygon_or_ring:
        return 0.0
    if _looks_like_ring(polygon_or_ring):
        return abs(signed_area_ring(polygon_or_ring))  # type: ignore[arg-type]
    polygon = polygon_or_ring  # type: ignore[assignment]
    if not polygon:
        return 0.0
    area = abs(signed_area_ring(polygon[0]))
    for hole in polygon[1:]:
        area -= abs(signed_area_ring(hole))
    return max(0.0, area)


def polygon_centroid(polygon_or_ring: list[Coordinate] | list[list[Coordinate]]) -> Coordinate:
    if not polygon_or_ring:
        return (0.0, 0.0)
    if _looks_like_ring(polygon_or_ring):
        return _ring_centroid(polygon_or_ring)  # type: ignore[arg-type]

    polygon = polygon_or_ring  # type: ignore[assignment]
    weighted_x = 0.0
    weighted_y = 0.0
    total_area = 0.0
    for index, ring in enumerate(polygon):
        signed_area = signed_area_ring(ring)
        weight = signed_area if index == 0 else -abs(signed_area)
        centroid = _ring_centroid(ring)
        weighted_x += centroid[0] * weight
        weighted_y += centroid[1] * weight
        total_area += weight
    if abs(total_area) <= EPSILON:
        points = [point for ring in polygon for point in ring]
        return _average_point(points)
    return weighted_x / total_area, weighted_y / total_area


def polygon_bbox(polygon_or_multipolygon: list[list[Coordinate]] | list[list[list[Coordinate]]]) -> tuple[float, float, float, float]:
    coords: list[Coordinate] = []
    if not polygon_or_multipolygon:
        raise ValueError("Polygon must contain coordinates")
    if _looks_like_polygon(polygon_or_multipolygon):
        coords = [coord for ring in polygon_or_multipolygon for coord in ring]  # type: ignore[union-attr]
    else:
        coords = [coord for polygon in polygon_or_multipolygon for ring in polygon for coord in ring]  # type: ignore[union-attr]
    if not coords:
        raise ValueError("Polygon must contain coordinates")
    return bbox_of_points(coords)


def is_ring_closed(points: list[Coordinate]) -> bool:
    return len(points) > 1 and same_point(points[0], points[-1])


def close_ring(points: list[Coordinate]) -> list[Coordinate]:
    if not points:
        return []
    if is_ring_closed(points):
        return list(points)
    return [*points, points[0]]


def detect_self_intersections(ring: list[Coordinate]) -> list[RingSelfIntersection]:
    closed = close_ring(ring)
    if len(closed) < 5:
        return []
    segments = list(zip(closed, closed[1:], strict=False))
    intersections: list[RingSelfIntersection] = []
    for first_index, (a1, a2) in enumerate(segments):
        for second_index, (b1, b2) in enumerate(segments[first_index + 1 :], start=first_index + 1):
            if _segments_are_adjacent(first_index, second_index, len(segments)):
                continue
            result = segment_intersection(a1, a2, b1, b2)
            if result.intersects:
                intersections.append(RingSelfIntersection(first_index, second_index, result))
    return intersections


def ring_orientation(ring: list[Coordinate]) -> RingOrientation:
    area = signed_area_ring(ring)
    if abs(area) <= EPSILON:
        return "degenerate"
    return "ccw" if area > 0 else "cw"


def normalize_polygon_orientation(
    polygon: list[list[Coordinate]],
    outer_orientation: Literal["ccw", "cw"] = "ccw",
) -> list[list[Coordinate]]:
    if not polygon:
        return []
    normalized: list[list[Coordinate]] = []
    desired_hole_orientation = "cw" if outer_orientation == "ccw" else "ccw"
    for index, ring in enumerate(polygon):
        closed = close_ring(ring)
        desired = outer_orientation if index == 0 else desired_hole_orientation
        current = ring_orientation(closed)
        if current != "degenerate" and current != desired:
            closed = list(reversed(closed))
        normalized.append(closed)
    return normalized


def convex_hull(points: list[Coordinate]) -> list[Coordinate]:
    unique = sorted(set(points))
    if len(unique) <= 1:
        return unique

    def cross(o: Coordinate, a: Coordinate, b: Coordinate) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[Coordinate] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= EPSILON:
            lower.pop()
        lower.append(point)
    upper: list[Coordinate] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= EPSILON:
            upper.pop()
        upper.append(point)
    hull = lower[:-1] + upper[:-1]
    return hull + [hull[0]] if hull else []


def _point_in_ring_raw(point: Coordinate, ring: list[Coordinate]) -> PointLocation:
    if len(ring) < 4:
        return "outside"
    x, y = point
    inside = False
    for start, end in zip(ring, ring[1:], strict=False):
        if on_segment(point, start, end):
            return "boundary"
        x1, y1 = start
        x2, y2 = end
        if (y1 > y) == (y2 > y):
            continue
        x_intersection = (x2 - x1) * (y - y1) / (y2 - y1) + x1
        if x < x_intersection:
            inside = not inside
    return "inside" if inside else "outside"


def _apply_boundary_policy(location: PointLocation, boundary_policy: BoundaryPolicy) -> PointLocation:
    if location != "boundary":
        return location
    return boundary_policy


def _ring_centroid(ring: list[Coordinate]) -> Coordinate:
    closed = close_ring(ring)
    area = signed_area_ring(closed)
    if abs(area) <= EPSILON:
        return _average_point(closed[:-1] if is_ring_closed(closed) else closed)

    cx = 0.0
    cy = 0.0
    for start, end in zip(closed, closed[1:], strict=False):
        cross = start[0] * end[1] - end[0] * start[1]
        cx += (start[0] + end[0]) * cross
        cy += (start[1] + end[1]) * cross
    factor = 1.0 / (6.0 * area)
    return cx * factor, cy * factor


def _average_point(points: list[Coordinate]) -> Coordinate:
    if not points:
        return (0.0, 0.0)
    return (sum(point[0] for point in points) / len(points), sum(point[1] for point in points) / len(points))


def _segments_are_adjacent(first_index: int, second_index: int, segment_count: int) -> bool:
    if abs(first_index - second_index) == 1:
        return True
    return {first_index, second_index} == {0, segment_count - 1}


def _looks_like_ring(value: object) -> bool:
    return bool(value) and isinstance(value, list) and bool(value[0]) and isinstance(value[0][0], (int, float))  # type: ignore[index]


def _looks_like_polygon(value: object) -> bool:
    return bool(value) and isinstance(value, list) and bool(value[0]) and _looks_like_ring(value[0])  # type: ignore[index]
