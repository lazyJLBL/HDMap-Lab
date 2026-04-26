from __future__ import annotations

from app.core.bbox import bbox_intersects, bbox_of_coords, bbox_of_polygon
from app.geometry_kernel import (
    ProjectionResult,
    angle_difference,
    bearing,
    haversine_distance,
    point_in_polygon,
    point_to_polyline_distance,
    point_to_segment_projection,
    polyline_length,
    segments_intersect,
)
from app.models.point import Coordinate

EARTH_RADIUS_M = 6_371_008.8


def point_on_segment(point: Coordinate, start: Coordinate, end: Coordinate, tolerance_m: float = 0.25) -> bool:
    projection = point_to_segment_projection(point, start, end)
    return projection.distance <= tolerance_m


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


__all__ = [
    "EARTH_RADIUS_M",
    "ProjectionResult",
    "angle_difference",
    "bearing",
    "haversine_distance",
    "point_in_polygon",
    "point_on_segment",
    "point_to_polyline_distance",
    "point_to_segment_projection",
    "polyline_intersects_polygon",
    "polyline_length",
    "segments_intersect",
]
