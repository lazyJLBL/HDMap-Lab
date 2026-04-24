from __future__ import annotations

from app.core.geometry import polyline_intersects_polygon
from app.models import RoadEdge
from app.models.point import Coordinate


def edges_intersecting_polygons(
    roads: list[RoadEdge],
    polygons: list[list[list[Coordinate]]],
) -> set[str]:
    blocked: set[str] = set()
    for road in roads:
        if any(polyline_intersects_polygon(road.geometry, polygon) for polygon in polygons):
            blocked.add(road.id)
    return blocked

