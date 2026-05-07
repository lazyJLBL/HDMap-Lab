from __future__ import annotations

from app.geometry_kernel.corridor import (
    approximate_polyline_buffer,
    corridor_contains_point,
    polyline_corridor_bbox,
    road_corridor_debug_geojson,
)
from app.geometry_kernel.simplification import (
    douglas_peucker,
    simplify_polyline_with_error_report,
    visvalingam_whyatt,
)


def test_douglas_peucker_keeps_tiny_angle_breakpoint_when_error_exceeds_tolerance() -> None:
    polyline = [(0, 0), (0.001, 0.0001), (0.002, 0)]
    simplified = douglas_peucker(polyline, tolerance_m=1.0)
    assert simplified == polyline


def test_visvalingam_whyatt_removes_low_area_points() -> None:
    polyline = [(0, 0), (0.001, 0.000001), (0.002, 0), (0.003, 0)]
    simplified = visvalingam_whyatt(polyline, threshold_area_m2=100.0)
    assert simplified[0] == polyline[0]
    assert simplified[-1] == polyline[-1]
    assert len(simplified) < len(polyline)


def test_simplification_error_report_fields() -> None:
    polyline = [(0, 0), (0.001, 0.00001), (0.002, 0)]
    report = simplify_polyline_with_error_report(polyline, tolerance_m=5.0)
    assert report.original_point_count == 3
    assert report.simplified_point_count <= 3
    assert 0 < report.compression_ratio <= 1
    assert report.max_error_estimate <= 5.0
    assert report.to_dict()["method"] == "douglas_peucker"


def test_corridor_approximation_and_debug_geojson() -> None:
    polyline = [(0, 0), (0.001, 0)]
    bbox = polyline_corridor_bbox(polyline, 20.0)
    assert bbox[0] < 0
    assert len(approximate_polyline_buffer(polyline, 20.0)[0]) == 5
    assert corridor_contains_point((0.0005, 0), polyline, 20.0)
    assert not corridor_contains_point((0.0005, 0.01), polyline, 20.0)
    debug = road_corridor_debug_geojson(polyline, 20.0)
    assert debug["type"] == "FeatureCollection"
    assert len(debug["features"]) == 2
