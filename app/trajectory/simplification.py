from __future__ import annotations

from app.geometry_kernel.polyline import simplify_polyline
from app.models.point import Coordinate


def simplify_trajectory(points: list[Coordinate], tolerance_m: float = 5.0) -> list[Coordinate]:
    return simplify_polyline(points, tolerance_m)
