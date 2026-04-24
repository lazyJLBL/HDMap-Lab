from __future__ import annotations

import math
from dataclasses import dataclass

from app.core.bbox import bbox_intersects, bbox_of_coords, bbox_of_polygon
from app.models.point import Coordinate

EARTH_RADIUS_M = 6_371_008.8


@dataclass(slots=True)
class ProjectionResult:
    projection: Coordinate
    distance: float
    segment_index: int
    t: float


def haversine_distance(a: Coordinate, b: Coordinate) -> float:
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def _to_xy(point: Coordinate, origin: Coordinate) -> tuple[float, float]:
    lon, lat = point
    origin_lon, origin_lat = origin
    x = math.radians(lon - origin_lon) * EARTH_RADIUS_M * math.cos(math.radians(origin_lat))
    y = math.radians(lat - origin_lat) * EARTH_RADIUS_M
    return x, y


def _from_xy(xy: tuple[float, float], origin: Coordinate) -> Coordinate:
    x, y = xy
    origin_lon, origin_lat = origin
    lon = origin_lon + math.degrees(x / (EARTH_RADIUS_M * math.cos(math.radians(origin_lat))))
    lat = origin_lat + math.degrees(y / EARTH_RADIUS_M)
    return lon, lat


def point_to_segment_projection(
    point: Coordinate,
    start: Coordinate,
    end: Coordinate,
    segment_index: int = 0,
) -> ProjectionResult:
    origin = point
    px, py = 0.0, 0.0
    sx, sy = _to_xy(start, origin)
    ex, ey = _to_xy(end, origin)
    vx, vy = ex - sx, ey - sy
    length_sq = vx * vx + vy * vy
    if length_sq == 0:
        projection_xy = (sx, sy)
        t = 0.0
    else:
        t = max(0.0, min(1.0, ((px - sx) * vx + (py - sy) * vy) / length_sq))
        projection_xy = (sx + t * vx, sy + t * vy)
    projection = _from_xy(projection_xy, origin)
    distance = math.hypot(px - projection_xy[0], py - projection_xy[1])
    return ProjectionResult(projection, distance, segment_index, t)


def point_to_polyline_distance(point: Coordinate, polyline: list[Coordinate]) -> ProjectionResult:
    if not polyline:
        raise ValueError("Polyline must contain at least one coordinate")
    if len(polyline) == 1:
        return ProjectionResult(polyline[0], haversine_distance(point, polyline[0]), 0, 0.0)
    best: ProjectionResult | None = None
    for idx, (start, end) in enumerate(zip(polyline, polyline[1:], strict=False)):
        result = point_to_segment_projection(point, start, end, idx)
        if best is None or result.distance < best.distance:
            best = result
    if best is None:
        raise ValueError("Polyline must contain at least one segment")
    return best


def polyline_length(polyline: list[Coordinate]) -> float:
    return sum(haversine_distance(start, end) for start, end in zip(polyline, polyline[1:], strict=False))


def point_on_segment(point: Coordinate, start: Coordinate, end: Coordinate, tolerance_m: float = 0.25) -> bool:
    projection = point_to_segment_projection(point, start, end)
    return projection.distance <= tolerance_m


def point_in_polygon(point: Coordinate, polygon: list[list[Coordinate]]) -> str:
    if not polygon or not polygon[0]:
        return "outside"
    if not bbox_intersects(bbox_of_polygon(polygon), (point[0], point[1], point[0], point[1])):
        return "outside"

    inside = False
    ring = polygon[0]
    for start, end in zip(ring, ring[1:], strict=False):
        if point_on_segment(point, start, end):
            return "boundary"
        x, y = point
        x1, y1 = start
        x2, y2 = end
        crosses = (y1 > y) != (y2 > y)
        if crosses:
            x_intersection = (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1
            if x <= x_intersection:
                inside = not inside

    if inside:
        for hole in polygon[1:]:
            if point_in_polygon(point, [hole]) in {"inside", "boundary"}:
                return "outside"
        return "inside"
    return "outside"


def bearing(a: Coordinate, b: Coordinate) -> float:
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def angle_difference(first: float, second: float) -> float:
    diff = abs((first - second + 180.0) % 360.0 - 180.0)
    return diff


def segments_intersect(a1: Coordinate, a2: Coordinate, b1: Coordinate, b2: Coordinate) -> bool:
    def orient(p: Coordinate, q: Coordinate, r: Coordinate) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def on_box(p: Coordinate, q: Coordinate, r: Coordinate) -> bool:
        return min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])

    o1 = orient(a1, a2, b1)
    o2 = orient(a1, a2, b2)
    o3 = orient(b1, b2, a1)
    o4 = orient(b1, b2, a2)
    eps = 1e-12
    if o1 * o2 < -eps and o3 * o4 < -eps:
        return True
    if abs(o1) <= eps and on_box(a1, b1, a2):
        return True
    if abs(o2) <= eps and on_box(a1, b2, a2):
        return True
    if abs(o3) <= eps and on_box(b1, a1, b2):
        return True
    if abs(o4) <= eps and on_box(b1, a2, b2):
        return True
    return False


def polyline_intersects_polygon(polyline: list[Coordinate], polygon: list[list[Coordinate]]) -> bool:
    if not polyline or not polygon or not polygon[0]:
        return False
    if not bbox_intersects(bbox_of_coords(polyline), bbox_of_polygon(polygon)):
        return False
    if any(point_in_polygon(coord, polygon) in {"inside", "boundary"} for coord in polyline):
        return True
    exterior = polygon[0]
    for line_start, line_end in zip(polyline, polyline[1:], strict=False):
        for poly_start, poly_end in zip(exterior, exterior[1:], strict=False):
            if segments_intersect(line_start, line_end, poly_start, poly_end):
                return True
    return False

