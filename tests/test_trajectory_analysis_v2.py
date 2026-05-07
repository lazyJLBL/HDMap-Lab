from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.trajectory import (
    angle_outlier_detection,
    directed_hausdorff_distance,
    discrete_frechet_distance,
    distance_jump_detection,
    dtw_alignment_path,
    dtw_distance,
    frechet_matching_pairs,
    hausdorff_distance,
    hausdorff_witness_points,
    route_deviation_detection,
    simplification_error_report,
    speed_outlier_detection,
)


def test_identical_trajectory_distances_are_zero() -> None:
    path = [(116.0, 39.0), (116.001, 39.0), (116.002, 39.0)]

    assert discrete_frechet_distance(path, path) == 0.0
    assert hausdorff_distance(path, path) == 0.0
    assert dtw_distance(path, path) == 0.0


def test_shifted_trajectory_distances_are_positive() -> None:
    first = [(116.0, 39.0), (116.001, 39.0), (116.002, 39.0)]
    shifted = [(116.0, 39.0005), (116.001, 39.0005), (116.002, 39.0005)]

    assert discrete_frechet_distance(first, shifted) > 0.0
    assert directed_hausdorff_distance(first, shifted) > 0.0
    assert dtw_distance(first, shifted) > 0.0


def test_frechet_and_hausdorff_witness_layers_are_geojson() -> None:
    first = [(116.0, 39.0), (116.001, 39.0), (116.002, 39.0)]
    second = [(116.0, 39.0), (116.002, 39.0)]

    frechet = frechet_matching_pairs(first, second)
    hausdorff = hausdorff_witness_points(first, second)

    assert frechet["matching_pairs"]
    assert frechet["debug_layers"]["frechet_witness"]["type"] == "FeatureCollection"
    assert hausdorff["witness_points"]
    assert hausdorff["debug_layers"]["hausdorff_witness"]["type"] == "FeatureCollection"


def test_dtw_alignment_path() -> None:
    first = [(116.0, 39.0), (116.001, 39.0), (116.002, 39.0)]
    second = [(116.0, 39.0), (116.002, 39.0)]

    alignment = dtw_alignment_path(first, second, window=2)

    assert alignment["distance_m"] >= 0.0
    assert alignment["alignment_path"][0] == {"path_a_index": 0, "path_b_index": 0}
    assert alignment["debug_layers"]["dtw_alignment"]["type"] == "FeatureCollection"


def test_simplification_error_report() -> None:
    path = [(116.0, 39.0), (116.0005, 39.00001), (116.001, 39.0), (116.002, 39.0)]

    report = simplification_error_report(path, tolerance_m=5.0)

    assert report["original_point_count"] == 4
    assert report["simplified_point_count"] < 4
    assert report["max_error_estimate"] <= 5.0


def test_outlier_detection_variants() -> None:
    path = [(116.0, 39.0), (116.001, 39.0), (116.5, 40.0), (116.002, 39.0)]
    angle_path = [(116.0, 39.0), (116.001, 39.0), (116.0, 39.0)]

    assert speed_outlier_detection(path, default_interval_s=1.0)
    assert distance_jump_detection(path, max_step_m=200.0)
    assert angle_outlier_detection(angle_path, sharp_angle_degrees=150.0)


def test_route_deviation_detection_outputs_debug_layers() -> None:
    route = [(116.0, 39.0), (116.002, 39.0)]
    trace = [(116.0, 39.0), (116.001, 39.001), (116.002, 39.0)]

    deviation = route_deviation_detection(trace, route, threshold_m=30.0)

    assert deviation["max_deviation_m"] > 30.0
    assert deviation["off_route_points"]
    assert deviation["debug_layers"]["off_route_points"]["type"] == "FeatureCollection"
    json.dumps(deviation["debug_layers"])


def test_trajectory_analyze_api_methods_and_debug_layers() -> None:
    client = TestClient(app)
    response = client.post(
        "/trajectory/analyze",
        json={
            "trajectory": {
                "id": "trace",
                "points": [
                    {"lon": 116.0, "lat": 39.0},
                    {"lon": 116.001, "lat": 39.001},
                    {"lon": 116.002, "lat": 39.0},
                ],
            },
            "reference_route": [[116.0, 39.0], [116.002, 39.0]],
            "methods": ["frechet", "hausdorff", "dtw", "simplification", "outlier", "deviation"],
            "return_debug_layers": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["distances"]["frechet_m"] >= 0.0
    assert payload["data"]["deviation"]["off_route_points"]
    assert payload["debug_layers"]["raw_trajectory"]["type"] == "FeatureCollection"
