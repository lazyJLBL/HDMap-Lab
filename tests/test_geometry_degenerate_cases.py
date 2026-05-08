from __future__ import annotations

from app.geometry_kernel.intersection import segment_intersection
from app.geometry_kernel.polygon import point_in_polygon
from app.geometry_kernel.predicates import Orientation, exact_orientation_fallback, on_segment, orientation


def test_collinear_segments_can_be_disjoint() -> None:
    result = segment_intersection((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0))

    assert not result.intersects
    assert result.relation == "collinear_disjoint"


def test_endpoint_intersection_is_classified_as_endpoint_touch() -> None:
    result = segment_intersection((0.0, 0.0), (1.0, 0.0), (1.0, 0.0), (1.0, 1.0))

    assert result.kind == "point"
    assert result.relation == "endpoint_touch"
    assert result.point == (1.0, 0.0)


def test_partial_overlap_returns_overlap_interval() -> None:
    result = segment_intersection((0.0, 0.0), (3.0, 0.0), (1.0, 0.0), (2.0, 0.0))

    assert result.kind == "overlap"
    assert result.relation == "overlap"
    assert result.overlap == ((1.0, 0.0), (2.0, 0.0))


def test_complete_overlap_keeps_the_shared_segment() -> None:
    result = segment_intersection((0.0, 0.0), (3.0, 0.0), (0.0, 0.0), (3.0, 0.0))

    assert result.kind == "overlap"
    assert result.overlap == ((0.0, 0.0), (3.0, 0.0))


def test_nearly_collinear_points_can_use_explicit_tolerance() -> None:
    assert orientation((0.0, 0.0), (1.0, 1.0), (2.0, 2.0 + 1e-10), eps=1e-8) == Orientation.COLLINEAR
    assert on_segment((1.0, 1.0 + 1e-10), (0.0, 0.0), (2.0, 2.0), eps=1e-8)


def test_zero_length_segment_intersects_when_point_lies_on_segment() -> None:
    result = segment_intersection((1.0, 1.0), (1.0, 1.0), (0.0, 1.0), (2.0, 1.0))

    assert result.kind == "point"
    assert result.relation == "touch"
    assert result.point == (1.0, 1.0)


def test_extremely_short_segment_is_treated_as_degenerate_point() -> None:
    result = segment_intersection((0.0, 0.0), (1e-14, 0.0), (0.0, -1.0), (0.0, 1.0))

    assert result.kind == "point"
    assert result.relation == "touch"
    assert result.point == (0.0, 0.0)


def test_large_coordinates_with_small_offset_keep_orientation_sign() -> None:
    a = (1_000_000_000.0, 1_000_000_000.0)
    b = (1_000_000_001.0, 1_000_000_000.000001)
    c = (1_000_000_002.0, 1_000_000_000.000003)

    assert orientation(a, b, c) == Orientation.COUNTER_CLOCKWISE
    assert exact_orientation_fallback(a, b, c) == Orientation.COUNTER_CLOCKWISE


def test_point_on_polygon_outer_boundary() -> None:
    polygon = [[(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0), (0.0, 0.0)]]

    assert point_in_polygon((0.0, 2.0), polygon) == "boundary"


def test_point_inside_polygon_hole_is_outside() -> None:
    polygon = [
        [(0.0, 0.0), (6.0, 0.0), (6.0, 6.0), (0.0, 6.0), (0.0, 0.0)],
        [(2.0, 2.0), (4.0, 2.0), (4.0, 4.0), (2.0, 4.0), (2.0, 2.0)],
    ]

    assert point_in_polygon((3.0, 3.0), polygon) == "outside"


def test_point_on_polygon_hole_boundary_is_boundary() -> None:
    polygon = [
        [(0.0, 0.0), (6.0, 0.0), (6.0, 6.0), (0.0, 6.0), (0.0, 0.0)],
        [(2.0, 2.0), (4.0, 2.0), (4.0, 4.0), (2.0, 4.0), (2.0, 2.0)],
    ]

    assert point_in_polygon((2.0, 3.0), polygon) == "boundary"
