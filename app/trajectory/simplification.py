from __future__ import annotations

from app.geometry_kernel.simplification import (
    douglas_peucker,
    simplify_polyline_with_error_report,
    visvalingam_whyatt,
)
from app.models.point import Coordinate


def simplify_trajectory(points: list[Coordinate], tolerance_m: float = 5.0) -> list[Coordinate]:
    return simplify_trajectory_rdp(points, tolerance_m)


def simplify_trajectory_rdp(points: list[Coordinate], tolerance_m: float = 5.0) -> list[Coordinate]:
    return douglas_peucker(points, tolerance_m)


def simplify_trajectory_vw(points: list[Coordinate], threshold_area_m2: float = 5.0) -> list[Coordinate]:
    return visvalingam_whyatt(points, threshold_area_m2)


def simplification_error_report(
    points: list[Coordinate],
    tolerance_m: float = 5.0,
    method: str = "rdp",
) -> dict:
    report = simplify_polyline_with_error_report(points, tolerance_m=tolerance_m, method=method)
    return {
        "method": report.method,
        "original_point_count": report.original_point_count,
        "simplified_point_count": report.simplified_point_count,
        "compression_ratio": report.compression_ratio,
        "max_error_estimate": report.max_error_estimate,
        "simplified": [[lon, lat] for lon, lat in report.simplified],
    }
