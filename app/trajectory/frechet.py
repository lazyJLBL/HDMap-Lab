from __future__ import annotations

from app.core.geojson import feature_collection
from app.geometry_kernel.polyline import haversine_distance
from app.models.point import Coordinate


def discrete_frechet_distance(first: list[Coordinate], second: list[Coordinate]) -> float:
    if not first or not second:
        return 0.0
    matrix = _frechet_matrix(first, second)
    return matrix[-1][-1]


def frechet_matching_pairs(first: list[Coordinate], second: list[Coordinate]) -> dict:
    if not first or not second:
        return {"distance_m": 0.0, "matching_pairs": [], "debug_layers": {}}
    matrix = _frechet_matrix(first, second)
    pairs = _backtrack_pairs(matrix)
    witness = max(pairs, key=lambda pair: haversine_distance(first[pair[0]], second[pair[1]]))
    return {
        "distance_m": matrix[-1][-1],
        "matching_pairs": [{"path_a_index": i, "path_b_index": j} for i, j in pairs],
        "witness_pair": {"path_a_index": witness[0], "path_b_index": witness[1]},
        "debug_layers": _debug_layers(first, second, pairs, witness),
    }


def _frechet_matrix(first: list[Coordinate], second: list[Coordinate]) -> list[list[float]]:
    rows = len(first)
    cols = len(second)
    matrix = [[0.0] * cols for _ in range(rows)]
    for i in range(rows):
        for j in range(cols):
            distance = haversine_distance(first[i], second[j])
            if i == 0 and j == 0:
                matrix[i][j] = distance
            elif i == 0:
                matrix[i][j] = max(matrix[i][j - 1], distance)
            elif j == 0:
                matrix[i][j] = max(matrix[i - 1][j], distance)
            else:
                matrix[i][j] = max(min(matrix[i - 1][j], matrix[i - 1][j - 1], matrix[i][j - 1]), distance)
    return matrix


def _backtrack_pairs(matrix: list[list[float]]) -> list[tuple[int, int]]:
    i = len(matrix) - 1
    j = len(matrix[0]) - 1
    pairs = [(i, j)]
    while i > 0 or j > 0:
        choices: list[tuple[float, int, int]] = []
        if i > 0:
            choices.append((matrix[i - 1][j], i - 1, j))
        if j > 0:
            choices.append((matrix[i][j - 1], i, j - 1))
        if i > 0 and j > 0:
            choices.append((matrix[i - 1][j - 1], i - 1, j - 1))
        _, i, j = min(choices, key=lambda item: item[0])
        pairs.append((i, j))
    pairs.reverse()
    return pairs


def _debug_layers(
    first: list[Coordinate],
    second: list[Coordinate],
    pairs: list[tuple[int, int]],
    witness: tuple[int, int],
) -> dict:
    pair_lines = [
        {
            "type": "Feature",
            "properties": {"path_a_index": i, "path_b_index": j},
            "geometry": {"type": "LineString", "coordinates": [[first[i][0], first[i][1]], [second[j][0], second[j][1]]]},
        }
        for i, j in pairs
    ]
    witness_line = {
        "type": "Feature",
        "properties": {"layer": "frechet_witness"},
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [first[witness[0]][0], first[witness[0]][1]],
                [second[witness[1]][0], second[witness[1]][1]],
            ],
        },
    }
    return {
        "frechet_pairs": feature_collection(pair_lines),
        "frechet_witness": feature_collection([witness_line]),
    }
