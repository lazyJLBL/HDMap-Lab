from __future__ import annotations

from app.core.bbox import bbox_intersects
from app.core.geometry import (
    haversine_distance,
    point_in_polygon,
    point_to_segment_projection,
    polyline_length,
)


def test_point_to_segment_projection_returns_distance_and_projection() -> None:
    result = point_to_segment_projection((116.400, 39.901), (116.390, 39.900), (116.410, 39.900))

    assert result.distance > 100
    assert abs(result.projection[0] - 116.400) < 0.0001
    assert abs(result.projection[1] - 39.900) < 0.0001


def test_point_in_polygon_inside_boundary_outside() -> None:
    polygon = [[(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)]]

    assert point_in_polygon((1, 1), polygon) == "inside"
    assert point_in_polygon((0, 1), polygon) == "boundary"
    assert point_in_polygon((3, 1), polygon) == "outside"


def test_bbox_intersection_and_polyline_length() -> None:
    assert bbox_intersects((0, 0, 2, 2), (1, 1, 3, 3))
    assert not bbox_intersects((0, 0, 1, 1), (2, 2, 3, 3))
    assert polyline_length([(116.39, 39.90), (116.40, 39.90)]) == haversine_distance(
        (116.39, 39.90), (116.40, 39.90)
    )

