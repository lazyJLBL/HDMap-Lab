from __future__ import annotations

import pytest

from app.geometry_kernel.polyline import (
    cumulative_lengths,
    cut_polyline_at_distance,
    heading_at_distance,
    interpolate_along_polyline,
    point_to_polyline_projection,
    point_to_segment_projection,
    polyline_length,
    split_polyline_at_points,
)


def test_point_to_segment_projection_fields() -> None:
    result = point_to_segment_projection((0.5, 0.001), (0, 0), (1, 0), segment_index=3)
    assert result.projected_point[0] == pytest.approx(0.5)
    assert abs(result.projected_point[1]) < 1e-9
    assert result.distance_m > 100
    assert result.segment_index == 3
    assert result.t == pytest.approx(0.5)
    assert result.along_track_distance > 0


def test_projection_handles_duplicate_points_and_zero_length_segments() -> None:
    polyline = [(0, 0), (0, 0), (1, 0)]
    result = point_to_polyline_projection((0.25, 0.001), polyline)
    assert result.segment_index == 1
    assert result.projected_point[0] == pytest.approx(0.25)
    assert result.t == pytest.approx(0.25)

    zero = point_to_segment_projection((0, 0.001), (0, 0), (0, 0))
    assert zero.t == 0.0
    assert zero.projected_point == (0, 0)


def test_length_interpolate_cut_and_heading() -> None:
    polyline = [(0, 0), (0.001, 0), (0.002, 0)]
    lengths = cumulative_lengths(polyline)
    assert len(lengths) == 3
    assert polyline_length(polyline) == pytest.approx(lengths[-1])
    mid = interpolate_along_polyline(polyline, lengths[-1] / 2)
    assert mid[0] == pytest.approx(0.001)
    left, right = cut_polyline_at_distance(polyline, lengths[-1] / 2)
    assert left[-1] == pytest.approx(right[0])
    assert heading_at_distance(polyline, 1.0) == pytest.approx(90.0)


def test_split_polyline_at_points_is_stable_by_along_track_order() -> None:
    polyline = [(0, 0), (0.003, 0)]
    split_points = [(0.002, 0.0001), (0.001, -0.0001)]
    parts = split_polyline_at_points(polyline, split_points)
    assert len(parts) == 3
    assert parts[0][-1][0] == pytest.approx(0.001, abs=1e-6)
    assert parts[1][-1][0] == pytest.approx(0.002, abs=1e-6)
