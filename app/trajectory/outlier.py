from __future__ import annotations

from app.geometry_kernel.polyline import angle_difference, bearing, haversine_distance
from app.models.point import Coordinate


def speed_outlier_detection(
    points: list[Coordinate],
    timestamps_s: list[float] | None = None,
    max_speed_mps: float = 55.0,
    default_interval_s: float = 1.0,
) -> list[dict]:
    outliers: list[dict] = []
    for index in range(1, len(points)):
        interval = _interval_seconds(index, timestamps_s, default_interval_s)
        speed = haversine_distance(points[index - 1], points[index]) / max(interval, 1e-6)
        if speed > max_speed_mps:
            outliers.append({"index": index, "speed_mps": speed, "coordinate": points[index], "type": "speed"})
    return outliers


def angle_outlier_detection(
    points: list[Coordinate],
    sharp_angle_degrees: float = 135.0,
    min_leg_m: float = 5.0,
) -> list[dict]:
    outliers: list[dict] = []
    for index in range(1, len(points) - 1):
        first_leg = haversine_distance(points[index - 1], points[index])
        second_leg = haversine_distance(points[index], points[index + 1])
        if first_leg < min_leg_m or second_leg < min_leg_m:
            continue
        first_heading = bearing(points[index - 1], points[index])
        second_heading = bearing(points[index], points[index + 1])
        angle = angle_difference(first_heading, second_heading)
        if angle >= sharp_angle_degrees:
            outliers.append({"index": index, "angle_degrees": angle, "coordinate": points[index], "type": "angle"})
    return outliers


def distance_jump_detection(points: list[Coordinate], max_step_m: float = 150.0) -> list[dict]:
    outliers: list[dict] = []
    for index in range(1, len(points)):
        distance = haversine_distance(points[index - 1], points[index])
        if distance > max_step_m:
            outliers.append({"index": index, "distance_m": distance, "coordinate": points[index], "type": "distance_jump"})
    return outliers


def map_matching_residual_outlier_detection(
    points: list[Coordinate],
    matched_points: list[Coordinate] | None = None,
    residuals_m: list[float] | None = None,
    threshold_m: float = 30.0,
) -> list[dict]:
    if residuals_m is None and matched_points is not None:
        residuals_m = [haversine_distance(point, matched) for point, matched in zip(points, matched_points, strict=False)]
    residuals_m = residuals_m or []
    return [
        {"index": index, "residual_m": residual, "coordinate": points[index], "type": "map_matching_residual"}
        for index, residual in enumerate(residuals_m[: len(points)])
        if residual > threshold_m
    ]


def detect_outliers(points: list[Coordinate], max_step_m: float = 150.0) -> list[int]:
    indices = {item["index"] for item in distance_jump_detection(points, max_step_m=max_step_m)}
    indices.update(item["index"] for item in angle_outlier_detection(points))
    return sorted(indices)


def _interval_seconds(index: int, timestamps_s: list[float] | None, default_interval_s: float) -> float:
    if timestamps_s is None or index >= len(timestamps_s):
        return default_interval_s
    return timestamps_s[index] - timestamps_s[index - 1]
