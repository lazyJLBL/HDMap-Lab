from __future__ import annotations

from app.geometry_kernel.polyline import point_to_polyline_distance, polyline_length
from app.models.point import Coordinate
from app.trajectory.dtw import dtw_distance
from app.trajectory.frechet import discrete_frechet_distance
from app.trajectory.hausdorff import hausdorff_distance
from app.trajectory.outlier import detect_outliers
from app.trajectory.simplification import simplify_trajectory


def analyze_trajectory(
    observed: list[Coordinate],
    reference: list[Coordinate] | None = None,
    simplify_tolerance_m: float = 5.0,
    deviation_threshold_m: float = 30.0,
) -> dict:
    simplified = simplify_trajectory(observed, simplify_tolerance_m)
    reference = reference or simplified
    deviations = [point_to_polyline_distance(point, reference).distance for point in observed] if reference else []
    return {
        "point_count": len(observed),
        "length_m": polyline_length(observed),
        "simplified_point_count": len(simplified),
        "outlier_indices": detect_outliers(observed),
        "deviation": {
            "max_m": max(deviations) if deviations else 0.0,
            "mean_m": sum(deviations) / len(deviations) if deviations else 0.0,
            "exceeds_threshold": [index for index, value in enumerate(deviations) if value > deviation_threshold_m],
        },
        "distances": {
            "frechet_m": discrete_frechet_distance(observed, reference),
            "hausdorff_m": hausdorff_distance(observed, reference),
            "dtw_m": dtw_distance(observed, reference),
        },
        "simplified": [[lon, lat] for lon, lat in simplified],
    }
