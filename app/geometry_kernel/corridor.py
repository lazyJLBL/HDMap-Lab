from __future__ import annotations

import math
from typing import Any

from app.geometry_kernel.polyline import EARTH_RADIUS_M, point_to_polyline_projection
from app.geometry_kernel.predicates import bbox_contains_point, bbox_of_points
from app.models.point import Coordinate


def polyline_corridor_bbox(polyline: list[Coordinate], radius_m: float) -> tuple[float, float, float, float]:
    if not polyline:
        raise ValueError("Polyline must contain at least one coordinate")
    min_lon, min_lat, max_lon, max_lat = bbox_of_points(polyline)
    mid_lat = (min_lat + max_lat) / 2.0
    lat_delta = math.degrees(radius_m / EARTH_RADIUS_M)
    lon_delta = math.degrees(radius_m / (EARTH_RADIUS_M * max(math.cos(math.radians(mid_lat)), 1e-12)))
    return min_lon - lon_delta, min_lat - lat_delta, max_lon + lon_delta, max_lat + lat_delta


def approximate_polyline_buffer(polyline: list[Coordinate], radius_m: float) -> list[list[Coordinate]]:
    """Return a conservative approximate buffer polygon around a polyline.

    This v2 kernel intentionally uses an expanded bbox corridor instead of a
    full offset-curve implementation. It is safe for broad-phase filtering and
    debug visualization, but it over-includes around bends and long diagonals.
    """

    if not polyline:
        return [[]]
    min_lon, min_lat, max_lon, max_lat = polyline_corridor_bbox(polyline, radius_m)
    return [
        [
            (min_lon, min_lat),
            (max_lon, min_lat),
            (max_lon, max_lat),
            (min_lon, max_lat),
            (min_lon, min_lat),
        ]
    ]


def corridor_contains_point(point: Coordinate, polyline: list[Coordinate], radius_m: float) -> bool:
    if not polyline:
        return False
    if not bbox_contains_point(polyline_corridor_bbox(polyline, radius_m), point):
        return False
    return point_to_polyline_projection(point, polyline).distance_m <= radius_m


def road_corridor_debug_geojson(polyline: list[Coordinate], radius_m: float) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    if polyline:
        features.append(
            {
                "type": "Feature",
                "properties": {"layer": "corridor_centerline", "radius_m": radius_m},
                "geometry": {"type": "LineString", "coordinates": [list(point) for point in polyline]},
            }
        )
        features.append(
            {
                "type": "Feature",
                "properties": {"layer": "approximate_corridor", "radius_m": radius_m, "approximation": "expanded_bbox"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[list(point) for point in ring] for ring in approximate_polyline_buffer(polyline, radius_m)],
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def corridor_bbox(polyline: list[Coordinate], radius_m: float) -> list[list[Coordinate]]:
    return approximate_polyline_buffer(polyline, radius_m)
