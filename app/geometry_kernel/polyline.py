from __future__ import annotations

import math
from dataclasses import dataclass

from app.models.point import Coordinate

EARTH_RADIUS_M = 6_371_008.8


@dataclass(slots=True)
class ProjectionResult:
    projected_point: Coordinate
    distance_m: float
    segment_index: int
    t: float
    offset_distance: float = 0.0
    along_track_distance: float = 0.0

    @property
    def projection(self) -> Coordinate:
        return self.projected_point

    @property
    def distance(self) -> float:
        return self.distance_m


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
        segment_length = 0.0
        signed_offset = math.hypot(projection_xy[0], projection_xy[1])
    else:
        t = max(0.0, min(1.0, (-(sx * vx + sy * vy)) / length_sq))
        projection_xy = (sx + t * vx, sy + t * vy)
        segment_length = math.sqrt(length_sq)
        cross = vx * (0.0 - sy) - vy * (0.0 - sx)
        sign = 0.0 if abs(cross) <= 1e-18 else math.copysign(1.0, cross)
        signed_offset = sign * math.hypot(projection_xy[0], projection_xy[1])
    projection = _from_xy(projection_xy, origin)
    return ProjectionResult(
        projected_point=projection,
        distance_m=math.hypot(projection_xy[0], projection_xy[1]),
        segment_index=segment_index,
        t=t,
        offset_distance=signed_offset,
        along_track_distance=t * segment_length,
    )


def point_to_polyline_projection(point: Coordinate, polyline: list[Coordinate]) -> ProjectionResult:
    if not polyline:
        raise ValueError("Polyline must contain at least one coordinate")
    if len(polyline) == 1:
        return ProjectionResult(polyline[0], haversine_distance(point, polyline[0]), 0, 0.0, 0.0, 0.0)

    lengths = cumulative_lengths(polyline)
    best: ProjectionResult | None = None
    for index, (start, end) in enumerate(zip(polyline, polyline[1:], strict=False)):
        candidate = point_to_segment_projection(point, start, end, index)
        along = lengths[index] + candidate.along_track_distance
        candidate = ProjectionResult(
            candidate.projected_point,
            candidate.distance_m,
            candidate.segment_index,
            candidate.t,
            candidate.offset_distance,
            along,
        )
        if best is None or candidate.distance_m < best.distance_m:
            best = candidate
    if best is None:
        raise ValueError("Polyline must contain at least one segment")
    return best


def point_to_polyline_distance(point: Coordinate, polyline: list[Coordinate]) -> ProjectionResult:
    return point_to_polyline_projection(point, polyline)


def cumulative_lengths(polyline: list[Coordinate]) -> list[float]:
    lengths = [0.0]
    total = 0.0
    for start, end in zip(polyline, polyline[1:], strict=False):
        total += haversine_distance(start, end)
        lengths.append(total)
    return lengths


def polyline_length(polyline: list[Coordinate]) -> float:
    return cumulative_lengths(polyline)[-1] if polyline else 0.0


def interpolate_along_polyline(polyline: list[Coordinate], distance_m: float) -> Coordinate:
    if not polyline:
        raise ValueError("Polyline must contain at least one coordinate")
    if len(polyline) == 1 or distance_m <= 0.0:
        return polyline[0]
    lengths = cumulative_lengths(polyline)
    if distance_m >= lengths[-1]:
        return polyline[-1]
    for index, (start, end) in enumerate(zip(polyline, polyline[1:], strict=False)):
        segment_length = lengths[index + 1] - lengths[index]
        if segment_length <= 1e-12:
            continue
        if lengths[index] <= distance_m <= lengths[index + 1]:
            t = (distance_m - lengths[index]) / segment_length
            return (start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t)
    return polyline[-1]


def cut_polyline_at_distance(polyline: list[Coordinate], distance_m: float) -> tuple[list[Coordinate], list[Coordinate]]:
    if not polyline:
        return [], []
    if len(polyline) == 1:
        return list(polyline), list(polyline)
    lengths = cumulative_lengths(polyline)
    if distance_m <= 0.0:
        return [polyline[0]], list(polyline)
    if distance_m >= lengths[-1]:
        return list(polyline), [polyline[-1]]

    cut_point = interpolate_along_polyline(polyline, distance_m)
    for index in range(len(lengths) - 1):
        if lengths[index] <= distance_m <= lengths[index + 1]:
            left = [*polyline[: index + 1]]
            if left[-1] != cut_point:
                left.append(cut_point)
            right = [cut_point]
            if cut_point == polyline[index + 1]:
                right.extend(polyline[index + 2 :])
            else:
                right.extend(polyline[index + 1 :])
            return left, right
    return list(polyline), [polyline[-1]]


def split_polyline_at_points(polyline: list[Coordinate], points: list[Coordinate]) -> list[list[Coordinate]]:
    if len(polyline) <= 1:
        return [list(polyline)] if polyline else []
    if not points:
        return [list(polyline)]

    events_by_segment: dict[int, list[tuple[float, int, Coordinate]]] = {}
    seen_distances: list[float] = []
    for order, point in enumerate(points):
        projection = point_to_polyline_projection(point, polyline)
        total_length = polyline_length(polyline)
        if projection.along_track_distance <= 1e-9 or projection.along_track_distance >= total_length - 1e-9:
            continue
        if any(abs(projection.along_track_distance - existing) <= 1e-7 for existing in seen_distances):
            continue
        seen_distances.append(projection.along_track_distance)
        events_by_segment.setdefault(projection.segment_index, []).append((projection.t, order, projection.projected_point))
    for events in events_by_segment.values():
        events.sort(key=lambda item: (item[0], item[1]))

    parts: list[list[Coordinate]] = []
    current = [polyline[0]]
    for index, (start, end) in enumerate(zip(polyline, polyline[1:], strict=False)):
        if current[-1] != start:
            current.append(start)
        for t, _order, split_point in events_by_segment.get(index, []):
            if t <= 1e-12 or t >= 1.0 - 1e-12:
                continue
            if current[-1] != split_point:
                current.append(split_point)
            parts.append(current)
            current = [split_point]
        if current[-1] != end:
            current.append(end)
    if current:
        parts.append(current)
    return [part for part in parts if len(part) >= 2]


def heading_at_distance(polyline: list[Coordinate], distance_m: float) -> float:
    if len(polyline) < 2:
        return 0.0
    lengths = cumulative_lengths(polyline)
    target = max(0.0, min(distance_m, lengths[-1]))
    selected: tuple[Coordinate, Coordinate] | None = None
    for index, (start, end) in enumerate(zip(polyline, polyline[1:], strict=False)):
        segment_length = lengths[index + 1] - lengths[index]
        if segment_length <= 1e-12:
            continue
        selected = (start, end)
        if lengths[index] <= target <= lengths[index + 1]:
            break
    if selected is None:
        return 0.0
    return bearing(selected[0], selected[1])


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
        distance = point_to_segment_projection(polyline[index], polyline[0], polyline[-1]).distance_m
        if distance > max_distance:
            max_distance = distance
            split_index = index
    if max_distance <= tolerance_m:
        return [polyline[0], polyline[-1]]
    left = simplify_polyline(polyline[: split_index + 1], tolerance_m)
    right = simplify_polyline(polyline[split_index:], tolerance_m)
    return left[:-1] + right
