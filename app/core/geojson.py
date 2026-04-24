from __future__ import annotations

from typing import Any, Iterable


def feature_collection(features: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": list(features)}


def normalize_coordinate(coord: list[float] | tuple[float, float]) -> tuple[float, float]:
    if len(coord) < 2:
        raise ValueError("Coordinate must contain lon and lat")
    return float(coord[0]), float(coord[1])


def normalize_linestring(coords: list[list[float]]) -> list[tuple[float, float]]:
    return [normalize_coordinate(coord) for coord in coords]


def normalize_polygon(coords: list[list[list[float]]]) -> list[list[tuple[float, float]]]:
    return [[normalize_coordinate(coord) for coord in ring] for ring in coords]

