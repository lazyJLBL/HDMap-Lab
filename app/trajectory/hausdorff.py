from __future__ import annotations

from app.geometry_kernel.polyline import haversine_distance
from app.models.point import Coordinate


def hausdorff_distance(first: list[Coordinate], second: list[Coordinate]) -> float:
    if not first or not second:
        return 0.0
    return max(_directed(first, second), _directed(second, first))


def _directed(first: list[Coordinate], second: list[Coordinate]) -> float:
    return max(min(haversine_distance(a, b) for b in second) for a in first)
