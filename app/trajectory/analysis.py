from __future__ import annotations

from typing import Any

from app.core.geojson import feature_collection
from app.geometry_kernel.polyline import polyline_length
from app.models.point import Coordinate
from app.trajectory.deviation import route_deviation_detection
from app.trajectory.dtw import dtw_alignment_path, dtw_distance
from app.trajectory.frechet import discrete_frechet_distance, frechet_matching_pairs
from app.trajectory.hausdorff import hausdorff_distance, hausdorff_witness_points
from app.trajectory.outlier import (
    angle_outlier_detection,
    detect_outliers,
    distance_jump_detection,
    map_matching_residual_outlier_detection,
    speed_outlier_detection,
)
from app.trajectory.simplification import simplification_error_report, simplify_trajectory_rdp, simplify_trajectory_vw


def analyze_trajectory(
    observed: list[Coordinate],
    reference: list[Coordinate] | None = None,
    simplify_tolerance_m: float = 5.0,
    deviation_threshold_m: float = 30.0,
    methods: list[str] | None = None,
    return_debug_layers: bool = True,
) -> dict[str, Any]:
    methods = methods or ["frechet", "hausdorff", "dtw", "simplification", "outlier", "deviation"]
    reference = reference or observed
    simplified = simplify_trajectory_rdp(observed, simplify_tolerance_m)
    result: dict[str, Any] = {
        "point_count": len(observed),
        "length_m": polyline_length(observed),
        "simplified_point_count": len(simplified),
        "simplified": [[lon, lat] for lon, lat in simplified],
        "debug_layers": _base_debug_layers(observed, simplified) if return_debug_layers else {},
    }
    distances: dict[str, float] = {}

    if "frechet" in methods:
        frechet = frechet_matching_pairs(observed, reference)
        result["frechet"] = frechet
        distances["frechet_m"] = frechet["distance_m"]
        _merge_debug(result, frechet.get("debug_layers", {}), return_debug_layers)
    else:
        distances["frechet_m"] = discrete_frechet_distance(observed, reference)

    if "hausdorff" in methods:
        hausdorff = hausdorff_witness_points(observed, reference)
        result["hausdorff"] = hausdorff
        distances["hausdorff_m"] = hausdorff["distance_m"]
        _merge_debug(result, hausdorff.get("debug_layers", {}), return_debug_layers)
    else:
        distances["hausdorff_m"] = hausdorff_distance(observed, reference)

    if "dtw" in methods:
        dtw = dtw_alignment_path(observed, reference)
        result["dtw"] = dtw
        distances["dtw_m"] = dtw["distance_m"]
        _merge_debug(result, dtw.get("debug_layers", {}), return_debug_layers)
    else:
        distances["dtw_m"] = dtw_distance(observed, reference)
    result["distances"] = distances

    if "simplification" in methods:
        result["simplification"] = {
            "rdp": simplification_error_report(observed, simplify_tolerance_m, method="rdp"),
            "visvalingam_whyatt": simplification_error_report(observed, simplify_tolerance_m, method="vw"),
            "simplified_vw": [[lon, lat] for lon, lat in simplify_trajectory_vw(observed, simplify_tolerance_m)],
        }

    if "outlier" in methods:
        outliers = {
            "speed": speed_outlier_detection(observed),
            "angle": angle_outlier_detection(observed),
            "distance_jump": distance_jump_detection(observed),
            "map_matching_residual": map_matching_residual_outlier_detection(observed),
        }
        result["outliers"] = outliers
        result["outlier_indices"] = sorted({item["index"] for values in outliers.values() for item in values})
    else:
        result["outlier_indices"] = detect_outliers(observed)

    if "deviation" in methods:
        deviation = route_deviation_detection(observed, reference, threshold_m=deviation_threshold_m)
        result["deviation"] = {
            "max_m": deviation["max_deviation_m"],
            "mean_m": deviation["mean_deviation_m"],
            "p95_m": deviation["p95_deviation_m"],
            "exceeds_threshold": [item["index"] for item in deviation["off_route_points"]],
            **deviation,
        }
        _merge_debug(result, deviation.get("debug_layers", {}), return_debug_layers)
    else:
        result["deviation"] = {"max_m": 0.0, "mean_m": 0.0, "exceeds_threshold": []}
    return result


def _base_debug_layers(observed: list[Coordinate], simplified: list[Coordinate]) -> dict[str, Any]:
    raw = {
        "type": "Feature",
        "properties": {"layer": "raw_trajectory"},
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in observed]},
    }
    simplified_feature = {
        "type": "Feature",
        "properties": {"layer": "simplified_trajectory"},
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in simplified]},
    }
    return {
        "raw_trajectory": feature_collection([raw]),
        "simplified_trajectory": feature_collection([simplified_feature]),
    }


def _merge_debug(result: dict[str, Any], layers: dict[str, Any], enabled: bool) -> None:
    if enabled:
        result.setdefault("debug_layers", {}).update(layers)
