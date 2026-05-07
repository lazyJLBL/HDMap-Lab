from __future__ import annotations

from app.core.geojson import feature_collection
from app.geometry_kernel.polyline import haversine_distance
from app.models.point import Coordinate


def directed_hausdorff_distance(first: list[Coordinate], second: list[Coordinate]) -> float:
    witness = _directed_witness(first, second)
    return witness["distance_m"]


def hausdorff_distance(first: list[Coordinate], second: list[Coordinate]) -> float:
    if not first or not second:
        return 0.0
    return max(directed_hausdorff_distance(first, second), directed_hausdorff_distance(second, first))


def hausdorff_witness_points(first: list[Coordinate], second: list[Coordinate]) -> dict:
    if not first or not second:
        return {"distance_m": 0.0, "witness_points": [], "debug_layers": {}}
    forward = _directed_witness(first, second)
    backward = _directed_witness(second, first)
    if backward["distance_m"] > forward["distance_m"]:
        witness = {
            "distance_m": backward["distance_m"],
            "source": "path_b",
            "point": backward["point"],
            "nearest": backward["nearest"],
        }
    else:
        witness = {
            "distance_m": forward["distance_m"],
            "source": "path_a",
            "point": forward["point"],
            "nearest": forward["nearest"],
        }
    return {
        "distance_m": witness["distance_m"],
        "witness_points": [witness],
        "debug_layers": _debug_layers(witness),
    }


def _directed_witness(first: list[Coordinate], second: list[Coordinate]) -> dict:
    if not first or not second:
        return {"distance_m": 0.0, "point": None, "nearest": None}
    best_distance = -1.0
    best_point = first[0]
    best_nearest = second[0]
    for point in first:
        nearest = min(second, key=lambda candidate: haversine_distance(point, candidate))
        distance = haversine_distance(point, nearest)
        if distance > best_distance:
            best_distance = distance
            best_point = point
            best_nearest = nearest
    return {"distance_m": best_distance, "point": best_point, "nearest": best_nearest}


def _debug_layers(witness: dict) -> dict:
    point = witness["point"]
    nearest = witness["nearest"]
    if point is None or nearest is None:
        return {}
    return {
        "hausdorff_witness": feature_collection(
            [
                {
                    "type": "Feature",
                    "properties": {"distance_m": witness["distance_m"], "source": witness["source"]},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[point[0], point[1]], [nearest[0], nearest[1]]],
                    },
                }
            ]
        )
    }
