from __future__ import annotations

import pytest

from app.geometry_kernel.predicates import (
    Orientation,
    bbox_contains_point,
    bbox_intersects,
    bbox_of_points,
    is_collinear,
    on_segment,
    orientation,
    orientation_value,
    robust_orientation,
    same_point,
    signed_area_ring,
)


def test_orientation_and_signed_area() -> None:
    assert orientation_value((0, 0), (1, 0), (1, 1)) > 0
    assert orientation((0, 0), (1, 0), (1, 1)) == Orientation.COUNTER_CLOCKWISE
    assert orientation((0, 0), (1, 0), (1, -1)) == Orientation.CLOCKWISE
    assert signed_area_ring([(0, 0), (2, 0), (2, 2), (0, 2)]) == pytest.approx(4.0)


def test_large_coordinates_small_delta_orientation() -> None:
    base = 1_000_000_000.0
    a = (base, base)
    b = (base + 1000.0, base + 1000.0)
    c = (base + 2000.0, base + 2000.001)
    assert robust_orientation(a, b, c) == Orientation.COUNTER_CLOCKWISE
    assert orientation(a, b, (base + 2000.0, base + 2000.0)) == Orientation.COLLINEAR


def test_collinear_on_segment_and_same_point_are_scale_aware() -> None:
    assert is_collinear((0, 0), (1, 1), (2, 2))
    assert on_segment((1, 1), (0, 0), (2, 2))
    assert not on_segment((3, 3), (0, 0), (2, 2))
    assert same_point((1_000_000_000.0, 1_000_000_000.0), (1_000_000_000.0 + 1e-7, 1_000_000_000.0))


def test_bbox_helpers() -> None:
    bbox = bbox_of_points([(0, 0), (2, 3), (-1, 4)])
    assert bbox == (-1, 0, 2, 4)
    assert bbox_intersects(bbox, (2, 4, 5, 5))
    assert not bbox_intersects(bbox, (3, 5, 6, 6))
    assert bbox_contains_point(bbox, (1, 1))
    assert not bbox_contains_point(bbox, (10, 1))
