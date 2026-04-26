from __future__ import annotations

from app.trajectory import analyze_trajectory, discrete_frechet_distance, dtw_distance, hausdorff_distance


def test_trajectory_distances_and_analysis() -> None:
    first = [(116.0, 39.0), (116.001, 39.0), (116.002, 39.0)]
    second = [(116.0, 39.0), (116.002, 39.0)]

    assert discrete_frechet_distance(first, second) > 0
    assert hausdorff_distance(first, second) > 0
    assert dtw_distance(first, second) > 0
    result = analyze_trajectory(first, second, simplify_tolerance_m=1.0)
    assert result["point_count"] == 3
    assert result["distances"]["frechet_m"] >= 0
