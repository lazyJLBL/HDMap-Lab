from __future__ import annotations

from app.geometry_kernel.predicates import EPSILON, on_segment
from app.models.point import Coordinate


def polygon_area(ring: list[Coordinate]) -> float:
    if len(ring) < 3:
        return 0.0
    area2 = 0.0
    for start, end in zip(ring, ring[1:], strict=False):
        area2 += start[0] * end[1] - end[0] * start[1]
    return area2 / 2.0


def polygon_centroid(ring: list[Coordinate]) -> Coordinate:
    area = polygon_area(ring)
    if abs(area) <= EPSILON:
        if not ring:
            return (0.0, 0.0)
        return (sum(point[0] for point in ring) / len(ring), sum(point[1] for point in ring) / len(ring))
    cx = 0.0
    cy = 0.0
    for start, end in zip(ring, ring[1:], strict=False):
        cross = start[0] * end[1] - end[0] * start[1]
        cx += (start[0] + end[0]) * cross
        cy += (start[1] + end[1]) * cross
    factor = 1.0 / (6.0 * area)
    return cx * factor, cy * factor


def polygon_bbox(polygon: list[list[Coordinate]]) -> tuple[float, float, float, float]:
    coords = [coord for ring in polygon for coord in ring]
    if not coords:
        raise ValueError("Polygon must contain coordinates")
    lons = [coord[0] for coord in coords]
    lats = [coord[1] for coord in coords]
    return min(lons), min(lats), max(lons), max(lats)


def point_in_polygon(point: Coordinate, polygon: list[list[Coordinate]]) -> str:
    if not polygon or not polygon[0]:
        return "outside"
    outer = _point_in_ring(point, polygon[0])
    if outer != "inside":
        return outer
    for hole in polygon[1:]:
        hole_status = _point_in_ring(point, hole)
        if hole_status == "boundary":
            return "boundary"
        if hole_status == "inside":
            return "outside"
    return "inside"


def _point_in_ring(point: Coordinate, ring: list[Coordinate]) -> str:
    if len(ring) < 3:
        return "outside"
    x, y = point
    inside = False
    for start, end in zip(ring, ring[1:], strict=False):
        if on_segment(point, start, end):
            return "boundary"
        x1, y1 = start
        x2, y2 = end
        crosses = (y1 > y) != (y2 > y)
        if crosses:
            x_intersection = (x2 - x1) * (y - y1) / ((y2 - y1) or EPSILON) + x1
            if x <= x_intersection + EPSILON:
                inside = not inside
    return "inside" if inside else "outside"


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
