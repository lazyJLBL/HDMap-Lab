from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.geometry_kernel.intersection import segment_intersection
from app.geometry_kernel.polygon import detect_self_intersections, point_in_polygon, polygon_area
from app.geometry_kernel.polyline import point_to_polyline_projection, point_to_segment_projection
from app.geometry_kernel.predicates import robust_orientation
from app.geometry_kernel.simplification import douglas_peucker
from app.models.point import Coordinate

DEFAULT_CASE_PATH = Path(__file__).resolve().parents[2] / "datasets" / "synthetic" / "geometry_degenerate_cases.json"


def load_geometry_cases(path: str | Path | None = None) -> list[dict[str, Any]]:
    case_path = Path(path) if path is not None else DEFAULT_CASE_PATH
    with case_path.open("r", encoding="utf-8") as file:
        cases = json.load(file)
    if not isinstance(cases, list):
        raise ValueError("Geometry case gallery must be a JSON list")
    return cases


def run_geometry_case(case: dict[str, Any]) -> dict[str, Any]:
    operation = case.get("input", {}).get("operation")
    expected = case.get("expected", {})
    actual, debug_layers = _run_operation(case)
    passed, reasons = _compare_expected(expected, actual)
    return {
        "case_id": case.get("id"),
        "category": case.get("category"),
        "description": case.get("description", ""),
        "passed": passed,
        "expected": expected,
        "actual": actual,
        "reasons": reasons,
        "operation": operation,
        "debug_layers": debug_layers,
    }


def run_all_geometry_cases(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    loaded_cases = load_geometry_cases() if cases is None else cases
    results = [run_geometry_case(case) for case in loaded_cases]
    return {"results": results, "summary": summarize_case_results(results)}


def cases_to_feature_collection(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    loaded_cases = load_geometry_cases() if cases is None else cases
    features: list[dict[str, Any]] = []
    for case in loaded_cases:
        features.extend(_input_features(case))
        debug_geojson = case.get("debug_geojson")
        if isinstance(debug_geojson, dict) and debug_geojson.get("type") == "FeatureCollection":
            features.extend(debug_geojson.get("features", []))
    return {"type": "FeatureCollection", "features": features}


def summarize_case_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for result in results if result.get("passed"))
    failed = total - passed
    pass_rate = passed / total if total else 1.0
    failed_cases = [result.get("case_id") for result in results if not result.get("passed")]
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
        "failed_cases": failed_cases,
    }


def _run_operation(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    input_data = case.get("input", {})
    operation = input_data.get("operation")
    if operation == "orientation":
        points = [_coord(point) for point in input_data["points"]]
        actual = {"orientation": robust_orientation(points[0], points[1], points[2]).name}
        return actual, {"case_geometry": _feature_collection(_input_features(case))}

    if operation == "segment_intersection":
        a1, a2 = [_coord(point) for point in input_data["segment_a"]]
        b1, b2 = [_coord(point) for point in input_data["segment_b"]]
        result = segment_intersection(a1, a2, b1, b2)
        actual = {
            "kind": result.kind,
            "relation": result.relation,
            "point": _point_to_list(result.point),
            "overlap": [_point_to_list(point) for point in result.overlap] if result.overlap else None,
        }
        features = _input_features(case)
        if result.point:
            features.append(_point_feature(result.point, case["id"], "actual_intersection"))
        if result.overlap:
            features.append(_line_feature(result.overlap, case["id"], "actual_overlap"))
        return actual, {"case_geometry": _feature_collection(features)}

    if operation == "point_in_polygon":
        polygon = [[_coord(point) for point in ring] for ring in input_data["polygon"]]
        points = {key: _coord(value) for key, value in input_data["points"].items()}
        actual = {key: point_in_polygon(point, polygon) for key, point in points.items()}
        actual["area"] = polygon_area(polygon)
        features = _input_features(case)
        features.extend(_point_feature(point, case["id"], f"query_{name}") for name, point in points.items())
        return actual, {"case_geometry": _feature_collection(features)}

    if operation == "detect_self_intersections":
        ring = [_coord(point) for point in input_data["ring"]]
        intersections = detect_self_intersections(ring)
        first = intersections[0].intersection if intersections else None
        actual = {
            "self_intersection_count": len(intersections),
            "kind": first.kind if first else None,
            "point": _point_to_list(first.point) if first else None,
        }
        features = _input_features(case)
        if first and first.point:
            features.append(_point_feature(first.point, case["id"], "self_intersection"))
        return actual, {"case_geometry": _feature_collection(features)}

    if operation == "point_to_polyline_projection":
        polyline = [_coord(point) for point in input_data["polyline"]]
        point = _coord(input_data["point"])
        projection = point_to_polyline_projection(point, polyline)
        actual = {
            "projected_point": _point_to_list(projection.projected_point),
            "distance_m": projection.distance_m,
            "segment_index": projection.segment_index,
            "t": projection.t,
            "along_track_distance": projection.along_track_distance,
        }
        features = _input_features(case)
        features.append(_point_feature(projection.projected_point, case["id"], "projection"))
        return actual, {"case_geometry": _feature_collection(features)}

    if operation == "point_to_segment_projection":
        start, end = [_coord(point) for point in input_data["segment"]]
        point = _coord(input_data["point"])
        projection = point_to_segment_projection(point, start, end)
        actual = {
            "projected_point": _point_to_list(projection.projected_point),
            "distance_m": projection.distance_m,
            "segment_index": projection.segment_index,
            "t": projection.t,
        }
        features = _input_features(case)
        features.append(_point_feature(projection.projected_point, case["id"], "projection"))
        return actual, {"case_geometry": _feature_collection(features)}

    if operation == "simplify_polyline":
        polyline = [_coord(point) for point in input_data["polyline"]]
        simplified = douglas_peucker(polyline, float(input_data.get("tolerance_m", 1.0)))
        actual = {
            "simplified_point_count": len(simplified),
            "simplified": [_point_to_list(point) for point in simplified],
        }
        features = _input_features(case)
        features.append(_line_feature(simplified, case["id"], "simplified"))
        return actual, {"case_geometry": _feature_collection(features)}

    raise ValueError(f"Unsupported geometry case operation: {operation}")


def _compare_expected(expected: dict[str, Any], actual: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for key, expected_value in expected.items():
        if key == "t_min":
            actual_t = float(actual.get("t", 0.0))
            if actual_t < float(expected_value):
                reasons.append(f"t={actual_t:.6f} is below expected minimum {expected_value}")
            continue
        if key == "t_max":
            actual_t = float(actual.get("t", 0.0))
            if actual_t > float(expected_value):
                reasons.append(f"t={actual_t:.6f} is above expected maximum {expected_value}")
            continue
        if key not in actual:
            reasons.append(f"Missing actual field {key}")
            continue
        if not _value_matches(expected_value, actual[key]):
            reasons.append(f"{key}: expected {expected_value!r}, got {actual[key]!r}")
    return not reasons, reasons


def _value_matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) <= 1e-6
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return False
        return all(_value_matches(left, right) for left, right in zip(expected, actual, strict=False))
    return expected == actual


def _input_features(case: dict[str, Any]) -> list[dict[str, Any]]:
    input_data = case.get("input", {})
    operation = input_data.get("operation")
    case_id = str(case.get("id", "unknown"))
    if operation == "orientation":
        return [_line_feature([_coord(point) for point in input_data["points"]], case_id, "input_points")]
    if operation == "segment_intersection":
        return [
            _line_feature([_coord(point) for point in input_data["segment_a"]], case_id, "segment_a"),
            _line_feature([_coord(point) for point in input_data["segment_b"]], case_id, "segment_b"),
        ]
    if operation == "point_in_polygon":
        polygon = [[_coord(point) for point in ring] for ring in input_data["polygon"]]
        return [_polygon_feature(polygon, case_id, "polygon")]
    if operation == "detect_self_intersections":
        return [_line_feature([_coord(point) for point in input_data["ring"]], case_id, "ring")]
    if operation == "point_to_polyline_projection":
        return [
            _line_feature([_coord(point) for point in input_data["polyline"]], case_id, "polyline"),
            _point_feature(_coord(input_data["point"]), case_id, "query_point"),
        ]
    if operation == "point_to_segment_projection":
        return [
            _line_feature([_coord(point) for point in input_data["segment"]], case_id, "segment"),
            _point_feature(_coord(input_data["point"]), case_id, "query_point"),
        ]
    if operation == "simplify_polyline":
        return [_line_feature([_coord(point) for point in input_data["polyline"]], case_id, "polyline")]
    return []


def _feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def _line_feature(points: list[Coordinate] | tuple[Coordinate, Coordinate], case_id: str, layer: str) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {"case_id": case_id, "layer": layer},
        "geometry": {"type": "LineString", "coordinates": [_point_to_list(point) for point in points]},
    }


def _polygon_feature(polygon: list[list[Coordinate]], case_id: str, layer: str) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {"case_id": case_id, "layer": layer},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[_point_to_list(point) for point in ring] for ring in polygon],
        },
    }


def _point_feature(point: Coordinate, case_id: str, layer: str) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {"case_id": case_id, "layer": layer},
        "geometry": {"type": "Point", "coordinates": _point_to_list(point)},
    }


def _coord(point: list[float] | tuple[float, float]) -> Coordinate:
    return (float(point[0]), float(point[1]))


def _point_to_list(point: Coordinate | None) -> list[float] | None:
    if point is None:
        return None
    return [float(point[0]), float(point[1])]
