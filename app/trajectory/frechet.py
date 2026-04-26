from __future__ import annotations

from functools import lru_cache

from app.geometry_kernel.polyline import haversine_distance
from app.models.point import Coordinate


def discrete_frechet_distance(first: list[Coordinate], second: list[Coordinate]) -> float:
    if not first or not second:
        return 0.0

    @lru_cache(maxsize=None)
    def ca(i: int, j: int) -> float:
        distance = haversine_distance(first[i], second[j])
        if i == 0 and j == 0:
            return distance
        if i == 0:
            return max(ca(0, j - 1), distance)
        if j == 0:
            return max(ca(i - 1, 0), distance)
        return max(min(ca(i - 1, j), ca(i - 1, j - 1), ca(i, j - 1)), distance)

    return ca(len(first) - 1, len(second) - 1)
