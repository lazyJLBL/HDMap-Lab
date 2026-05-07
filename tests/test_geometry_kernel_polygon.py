from __future__ import annotations

import pytest

from app.geometry_kernel.polygon import (
    close_ring,
    detect_self_intersections,
    is_ring_closed,
    normalize_polygon_orientation,
    point_in_multipolygon,
    point_in_polygon,
    point_in_ring,
    polygon_area,
    polygon_bbox,
    polygon_centroid,
    ring_orientation,
)


def test_point_in_ring_boundary_policy() -> None:
    ring = [(0, 0), (2, 0), (2, 2), (0, 2)]
    assert point_in_ring((1, 1), ring) == "inside"
    assert point_in_ring((0, 1), ring) == "boundary"
    assert point_in_ring((0, 1), ring, boundary_policy="inside") == "inside"
    assert point_in_ring((3, 1), ring) == "outside"


def test_polygon_with_hole() -> None:
    polygon = [
        [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)],
        [(1, 1), (1, 3), (3, 3), (3, 1), (1, 1)],
    ]
    assert point_in_polygon((0.5, 0.5), polygon) == "inside"
    assert point_in_polygon((2, 2), polygon) == "outside"
    assert point_in_polygon((1, 2), polygon) == "boundary"
    assert polygon_area(polygon) == pytest.approx(12.0)
    assert polygon_bbox(polygon) == (0, 0, 4, 4)


def test_multipolygon_basic_support() -> None:
    multipolygon = [
        [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]],
        [[(2, 2), (3, 2), (3, 3), (2, 3), (2, 2)]],
    ]
    assert point_in_multipolygon((0.5, 0.5), multipolygon) == "inside"
    assert point_in_multipolygon((2.5, 2.5), multipolygon) == "inside"
    assert point_in_multipolygon((1.5, 1.5), multipolygon) == "outside"


def test_ring_orientation_and_normalization() -> None:
    clockwise = [(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]
    assert ring_orientation(clockwise) == "cw"
    normalized = normalize_polygon_orientation([clockwise])
    assert ring_orientation(normalized[0]) == "ccw"
    assert is_ring_closed(close_ring(clockwise[:-1]))


def test_self_intersecting_bowtie_polygon() -> None:
    bowtie = [(0, 0), (2, 2), (0, 2), (2, 0), (0, 0)]
    intersections = detect_self_intersections(bowtie)
    assert len(intersections) == 1
    assert intersections[0].intersection.kind == "point"
    assert intersections[0].intersection.point == (1.0, 1.0)


def test_centroid_degenerate_ring_falls_back_to_average() -> None:
    assert polygon_centroid([(0, 0), (1, 1), (2, 2)]) == pytest.approx((1.0, 1.0))
