from __future__ import annotations

from app.geometry_kernel.intersection import (
    classify_segment_intersection,
    intersection_point,
    line_segment_relation,
    overlapping_segment,
    segment_intersection,
)


def test_crossing_segments() -> None:
    result = segment_intersection((0, 0), (2, 2), (0, 2), (2, 0))
    assert result.kind == "point"
    assert result.relation == "cross"
    assert result.point == (1.0, 1.0)


def test_endpoint_touch_segments() -> None:
    result = classify_segment_intersection((0, 0), (1, 1), (1, 1), (2, 0))
    assert result.kind == "point"
    assert result.relation == "endpoint_touch"
    assert result.point == (1, 1)


def test_t_junction_touch() -> None:
    result = segment_intersection((0, 0), (2, 0), (1, -1), (1, 0))
    assert result.kind == "point"
    assert result.relation == "touch"
    assert result.point == (1, 0)


def test_overlapping_segments_same_and_reverse_direction() -> None:
    result = segment_intersection((0, 0), (3, 0), (1, 0), (4, 0))
    assert result.kind == "overlap"
    assert result.relation == "overlap"
    assert result.overlap == ((1, 0), (3, 0))

    reversed_result = segment_intersection((3, 0), (0, 0), (1, 0), (4, 0))
    assert reversed_result.kind == "overlap"
    assert reversed_result.overlap == ((1, 0), (3, 0))


def test_collinear_disjoint_and_parallel_disjoint() -> None:
    collinear = segment_intersection((0, 0), (1, 0), (2, 0), (3, 0))
    assert collinear.kind == "none"
    assert collinear.relation == "collinear_disjoint"
    assert line_segment_relation((0, 0), (1, 0), (0, 1), (1, 1)) == "disjoint"


def test_almost_parallel_segments_do_not_create_false_intersection() -> None:
    result = segment_intersection((0, 0), (1_000_000, 1), (0, 2), (1_000_000, 3.000001))
    assert result.kind == "none"


def test_intersection_helpers() -> None:
    assert intersection_point((0, 0), (2, 2), (0, 2), (2, 0)) == (1.0, 1.0)
    assert overlapping_segment((0, 0), (3, 0), (1, 0), (2, 0)) == ((1, 0), (2, 0))
