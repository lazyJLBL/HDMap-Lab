from __future__ import annotations

from math import inf

from app.geometry_kernel.polyline import haversine_distance
from app.models.point import Coordinate


def dtw_distance(first: list[Coordinate], second: list[Coordinate]) -> float:
    if not first or not second:
        return 0.0
    rows = len(first) + 1
    cols = len(second) + 1
    dp = [[inf] * cols for _ in range(rows)]
    dp[0][0] = 0.0
    for i in range(1, rows):
        for j in range(1, cols):
            cost = haversine_distance(first[i - 1], second[j - 1])
            dp[i][j] = cost + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[-1][-1]
