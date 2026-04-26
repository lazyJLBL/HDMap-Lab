from __future__ import annotations

from app.geometry_kernel.polyline import haversine_distance
from app.models.point import Coordinate


def detect_outliers(points: list[Coordinate], max_step_m: float = 150.0) -> list[int]:
    if len(points) < 3:
        return []
    outliers: list[int] = []
    for index in range(1, len(points) - 1):
        prev_distance = haversine_distance(points[index - 1], points[index])
        next_distance = haversine_distance(points[index], points[index + 1])
        bypass_distance = haversine_distance(points[index - 1], points[index + 1])
        if prev_distance > max_step_m and next_distance > max_step_m and bypass_distance < max_step_m:
            outliers.append(index)
    return outliers
