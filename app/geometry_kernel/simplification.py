from __future__ import annotations

import heapq
from dataclasses import dataclass

from app.geometry_kernel.polyline import (
    _to_xy,
    point_to_polyline_projection,
    point_to_segment_projection,
    simplify_polyline,
)
from app.models.point import Coordinate


@dataclass(slots=True)
class SimplificationResult:
    simplified: list[Coordinate]
    original_point_count: int
    simplified_point_count: int
    compression_ratio: float
    max_error_estimate: float
    method: str

    def to_dict(self) -> dict[str, object]:
        return {
            "simplified": [list(point) for point in self.simplified],
            "original_point_count": self.original_point_count,
            "simplified_point_count": self.simplified_point_count,
            "compression_ratio": self.compression_ratio,
            "max_error_estimate": self.max_error_estimate,
            "method": self.method,
        }


def douglas_peucker(polyline: list[Coordinate], tolerance_m: float) -> list[Coordinate]:
    return simplify_polyline(polyline, tolerance_m)


def visvalingam_whyatt(
    polyline: list[Coordinate],
    threshold_area_m2: float,
    min_points: int = 2,
) -> list[Coordinate]:
    if len(polyline) <= min_points or len(polyline) <= 2:
        return list(polyline)

    origin = polyline[0]
    xy = [_to_xy(point, origin) for point in polyline]
    active = [True] * len(polyline)
    previous = [index - 1 for index in range(len(polyline))]
    next_index = [index + 1 for index in range(len(polyline))]
    next_index[-1] = -1
    heap: list[tuple[float, int]] = []
    for index in range(1, len(polyline) - 1):
        heapq.heappush(heap, (_triangle_area(xy[previous[index]], xy[index], xy[next_index[index]]), index))

    remaining = len(polyline)
    while heap and remaining > min_points:
        area, index = heapq.heappop(heap)
        if not active[index]:
            continue
        prev_index = previous[index]
        nxt_index = next_index[index]
        if prev_index < 0 or nxt_index < 0:
            continue
        current_area = _triangle_area(xy[prev_index], xy[index], xy[nxt_index])
        if abs(current_area - area) > 1e-9:
            heapq.heappush(heap, (current_area, index))
            continue
        if current_area > threshold_area_m2:
            break
        active[index] = False
        remaining -= 1
        next_index[prev_index] = nxt_index
        previous[nxt_index] = prev_index
        if previous[prev_index] >= 0:
            heapq.heappush(heap, (_triangle_area(xy[previous[prev_index]], xy[prev_index], xy[nxt_index]), prev_index))
        if next_index[nxt_index] >= 0:
            heapq.heappush(heap, (_triangle_area(xy[prev_index], xy[nxt_index], xy[next_index[nxt_index]]), nxt_index))

    return [point for point, keep in zip(polyline, active, strict=False) if keep]


def simplify_polyline_with_error_report(
    polyline: list[Coordinate],
    tolerance_m: float = 1.0,
    method: str = "douglas_peucker",
    threshold_area_m2: float | None = None,
) -> SimplificationResult:
    if method in {"douglas_peucker", "rdp"}:
        simplified = douglas_peucker(polyline, tolerance_m)
        method_name = "douglas_peucker"
    elif method in {"visvalingam_whyatt", "vw"}:
        simplified = visvalingam_whyatt(polyline, threshold_area_m2 if threshold_area_m2 is not None else tolerance_m)
        method_name = "visvalingam_whyatt"
    else:
        raise ValueError(f"Unsupported simplification method: {method}")

    original_count = len(polyline)
    simplified_count = len(simplified)
    compression_ratio = (simplified_count / original_count) if original_count else 1.0
    max_error = _max_simplification_error(polyline, simplified)
    return SimplificationResult(
        simplified=simplified,
        original_point_count=original_count,
        simplified_point_count=simplified_count,
        compression_ratio=compression_ratio,
        max_error_estimate=max_error,
        method=method_name,
    )


def _triangle_area(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2.0


def _max_simplification_error(original: list[Coordinate], simplified: list[Coordinate]) -> float:
    if not original or not simplified:
        return 0.0
    if len(simplified) == 1:
        return max(point_to_segment_projection(point, simplified[0], simplified[0]).distance_m for point in original)
    return max(point_to_polyline_projection(point, simplified).distance_m for point in original)


__all__ = [
    "SimplificationResult",
    "douglas_peucker",
    "simplify_polyline",
    "simplify_polyline_with_error_report",
    "visvalingam_whyatt",
]
