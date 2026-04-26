from __future__ import annotations

from app.geometry_kernel import (
    Orientation,
    convex_hull,
    orientation,
    point_in_polygon,
    polygon_area,
    polygon_centroid,
    segment_intersection,
    simplify_polyline,
)


def test_orientation_and_segment_degenerate_cases() -> None:
    assert orientation((0, 0), (1, 1), (2, 2)) == Orientation.COLLINEAR
    assert segment_intersection((0, 0), (2, 0), (1, 0), (3, 0)).kind == "overlap"
    endpoint = segment_intersection((0, 0), (1, 1), (1, 1), (2, 0))
    assert endpoint.kind == "point"
    assert endpoint.point == (1, 1)


def test_polygon_holes_area_centroid_and_hull() -> None:
    polygon = [
        [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)],
        [(1, 1), (2, 1), (2, 2), (1, 2), (1, 1)],
    ]
    assert point_in_polygon((0.5, 0.5), polygon) == "inside"
    assert point_in_polygon((1.5, 1.5), polygon) == "outside"
    assert polygon_area(polygon[0]) == 16
    assert polygon_centroid(polygon[0]) == (2, 2)
    assert convex_hull([(0, 0), (1, 0), (0, 1), (0.2, 0.2)])[0] == (0, 0)


def test_polyline_simplification_keeps_shape_breakpoints() -> None:
    simplified = simplify_polyline([(0, 0), (1, 0.001), (2, 0)], tolerance_m=10)
    assert len(simplified) == 3
