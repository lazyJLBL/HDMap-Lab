from __future__ import annotations

from app.core.geojson import feature_collection
from app.geometry_kernel.polyline import point_to_polyline_projection
from app.models.point import Coordinate


def route_deviation_detection(
    trajectory: list[Coordinate],
    reference_route: list[Coordinate],
    threshold_m: float = 30.0,
) -> dict:
    if not trajectory or not reference_route:
        return {
            "deviation_segments": [],
            "max_deviation_m": 0.0,
            "mean_deviation_m": 0.0,
            "p95_deviation_m": 0.0,
            "off_route_points": [],
            "debug_layers": {},
        }
    deviations = []
    for index, point in enumerate(trajectory):
        projection = point_to_polyline_projection(point, reference_route)
        deviations.append(
            {
                "index": index,
                "point": point,
                "projected_point": projection.projected_point,
                "distance_m": projection.distance_m,
                "along_track_distance": projection.along_track_distance,
            }
        )
    off_route = [item for item in deviations if item["distance_m"] > threshold_m]
    return {
        "deviation_segments": _segments(off_route),
        "max_deviation_m": max(item["distance_m"] for item in deviations),
        "mean_deviation_m": sum(item["distance_m"] for item in deviations) / len(deviations),
        "p95_deviation_m": _percentile([item["distance_m"] for item in deviations], 0.95),
        "off_route_points": off_route,
        "debug_layers": _debug_layers(trajectory, reference_route, off_route),
    }


def _segments(off_route: list[dict]) -> list[dict]:
    if not off_route:
        return []
    segments: list[dict] = []
    start = off_route[0]["index"]
    prev = start
    max_distance = off_route[0]["distance_m"]
    for item in off_route[1:]:
        if item["index"] == prev + 1:
            prev = item["index"]
            max_distance = max(max_distance, item["distance_m"])
            continue
        segments.append({"start_index": start, "end_index": prev, "max_deviation_m": max_distance})
        start = prev = item["index"]
        max_distance = item["distance_m"]
    segments.append({"start_index": start, "end_index": prev, "max_deviation_m": max_distance})
    return segments


def _debug_layers(
    trajectory: list[Coordinate],
    reference_route: list[Coordinate],
    off_route: list[dict],
) -> dict:
    raw = {
        "type": "Feature",
        "properties": {"layer": "raw_trajectory"},
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in trajectory]},
    }
    reference = {
        "type": "Feature",
        "properties": {"layer": "reference_route"},
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in reference_route]},
    }
    points = [
        {
            "type": "Feature",
            "properties": {"index": item["index"], "distance_m": item["distance_m"], "severity": "warning"},
            "geometry": {"type": "Point", "coordinates": [item["point"][0], item["point"][1]]},
        }
        for item in off_route
    ]
    residuals = [
        {
            "type": "Feature",
            "properties": {"index": item["index"], "distance_m": item["distance_m"]},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [item["point"][0], item["point"][1]],
                    [item["projected_point"][0], item["projected_point"][1]],
                ],
            },
        }
        for item in off_route
    ]
    return {
        "raw_trajectory": feature_collection([raw]),
        "reference_route": feature_collection([reference]),
        "off_route_points": feature_collection(points),
        "deviation_residuals": feature_collection(residuals),
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, round((len(values) - 1) * percentile))]
