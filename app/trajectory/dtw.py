from __future__ import annotations

from math import inf
from typing import Callable

from app.core.geojson import feature_collection
from app.geometry_kernel.polyline import haversine_distance
from app.models.point import Coordinate

DistanceFunction = Callable[[Coordinate, Coordinate], float]


def dtw_distance(
    first: list[Coordinate],
    second: list[Coordinate],
    distance_fn: DistanceFunction | None = None,
    window: int | None = None,
) -> float:
    return _dtw(first, second, distance_fn or haversine_distance, window)[0]


def dtw_alignment_path(
    first: list[Coordinate],
    second: list[Coordinate],
    distance_fn: DistanceFunction | None = None,
    window: int | None = None,
) -> dict:
    if not first or not second:
        return {"distance_m": 0.0, "alignment_path": [], "debug_layers": {}}
    distance, dp = _dtw(first, second, distance_fn or haversine_distance, window)
    i = len(first)
    j = len(second)
    path: list[tuple[int, int]] = []
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        options = [(dp[i - 1][j], i - 1, j), (dp[i][j - 1], i, j - 1), (dp[i - 1][j - 1], i - 1, j - 1)]
        _, i, j = min(options, key=lambda item: item[0])
    path.reverse()
    return {
        "distance_m": distance,
        "alignment_path": [{"path_a_index": i, "path_b_index": j} for i, j in path],
        "debug_layers": _debug_layers(first, second, path),
    }


def _dtw(
    first: list[Coordinate],
    second: list[Coordinate],
    distance_fn: DistanceFunction,
    window: int | None,
) -> tuple[float, list[list[float]]]:
    if not first or not second:
        return 0.0, [[0.0]]
    rows = len(first) + 1
    cols = len(second) + 1
    window = max(window if window is not None else max(len(first), len(second)), abs(len(first) - len(second)))
    dp = [[inf] * cols for _ in range(rows)]
    dp[0][0] = 0.0
    for i in range(1, rows):
        start = max(1, i - window)
        end = min(cols, i + window + 1)
        for j in range(start, end):
            cost = distance_fn(first[i - 1], second[j - 1])
            dp[i][j] = cost + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[-1][-1], dp


def _debug_layers(first: list[Coordinate], second: list[Coordinate], path: list[tuple[int, int]]) -> dict:
    lines = [
        {
            "type": "Feature",
            "properties": {"path_a_index": i, "path_b_index": j},
            "geometry": {"type": "LineString", "coordinates": [[first[i][0], first[i][1]], [second[j][0], second[j][1]]]},
        }
        for i, j in path
    ]
    return {"dtw_alignment": feature_collection(lines)}
