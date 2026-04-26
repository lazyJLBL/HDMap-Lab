from __future__ import annotations

import math
from dataclasses import dataclass

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
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
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
    cos_lat = max(math.cos(math.radians(origin_lat)), 1e-12)
    lon = origin_lon + math.degrees(x / (EARTH_RADIUS_M * cos_lat))
    lat = origin_lat + math.degrees(y / EARTH_RADIUS_M)
    return lon, lat


def point_to_segment_projection(
    point: Coordinate,
    start: Coordinate,
    end: Coordinate,
    segment_index: int = 0,
) -> ProjectionResult:
    origin = point
    sx, sy = _to_xy(start, origin)
    ex, ey = _to_xy(end, origin)
    vx, vy = ex - sx, ey - sy
    length_sq = vx * vx + vy * vy
    if length_sq <= 1e-18:
        projection_xy = (sx, sy)
        t = 0.0
    else:
        t = max(0.0, min(1.0, (-(sx * vx + sy * vy)) / length_sq))
        projection_xy = (sx + t * vx, sy + t * vy)
    projection = _from_xy(projection_xy, origin)
    return ProjectionResult(projection, math.hypot(projection_xy[0], projection_xy[1]), segment_index, t)


def point_to_polyline_distance(point: Coordinate, polyline: list[Coordinate]) -> ProjectionResult:
    if not polyline:
        raise ValueError("Polyline must contain at least one coordinate")
    if len(polyline) == 1:
        return ProjectionResult(polyline[0], haversine_distance(point, polyline[0]), 0, 0.0)
    best: ProjectionResult | None = None
    for index, (start, end) in enumerate(zip(polyline, polyline[1:], strict=False)):
        candidate = point_to_segment_projection(point, start, end, index)
        if best is None or candidate.distance < best.distance:
            best = candidate
    if best is None:
        raise ValueError("Polyline must contain at least one segment")
    return best


def polyline_length(polyline: list[Coordinate]) -> float:
    return sum(haversine_distance(start, end) for start, end in zip(polyline, polyline[1:], strict=False))


def bearing(a: Coordinate, b: Coordinate) -> float:
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def angle_difference(first: float, second: float) -> float:
    return abs((first - second + 180.0) % 360.0 - 180.0)


def simplify_polyline(polyline: list[Coordinate], tolerance_m: float) -> list[Coordinate]:
    if len(polyline) <= 2:
        return list(polyline)
    max_distance = -1.0
    split_index = 0
    for index in range(1, len(polyline) - 1):
        distance = point_to_segment_projection(polyline[index], polyline[0], polyline[-1]).distance
        if distance > max_distance:
            max_distance = distance
            split_index = index
    if max_distance <= tolerance_m:
        return [polyline[0], polyline[-1]]
    left = simplify_polyline(polyline[: split_index + 1], tolerance_m)
    right = simplify_polyline(polyline[split_index:], tolerance_m)
    return left[:-1] + right
