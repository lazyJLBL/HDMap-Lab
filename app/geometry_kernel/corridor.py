from __future__ import annotations

import math

from app.models.point import Coordinate

EARTH_RADIUS_M = 6_371_008.8


def corridor_bbox(polyline: list[Coordinate], radius_m: float) -> list[list[Coordinate]]:
    """A conservative first-pass road corridor as an expanded bbox polygon."""

    if not polyline:
        return [[]]
    min_lon = min(point[0] for point in polyline)
    max_lon = max(point[0] for point in polyline)
    min_lat = min(point[1] for point in polyline)
    max_lat = max(point[1] for point in polyline)
    mid_lat = (min_lat + max_lat) / 2.0
    lat_delta = math.degrees(radius_m / EARTH_RADIUS_M)
    lon_delta = math.degrees(radius_m / (EARTH_RADIUS_M * max(math.cos(math.radians(mid_lat)), 1e-12)))
    ring = [
        (min_lon - lon_delta, min_lat - lat_delta),
        (max_lon + lon_delta, min_lat - lat_delta),
        (max_lon + lon_delta, max_lat + lat_delta),
        (min_lon - lon_delta, max_lat + lat_delta),
        (min_lon - lon_delta, min_lat - lat_delta),
    ]
    return [ring]
