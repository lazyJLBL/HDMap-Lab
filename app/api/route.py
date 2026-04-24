from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.geojson import normalize_coordinate, normalize_polygon
from app.routing.astar import shortest_path_astar
from app.routing.constraints import edges_intersecting_polygons
from app.routing.dijkstra import PathResult, shortest_path
from app.schemas import RouteRequest
from app.storage.runtime import get_runtime

router = APIRouter(prefix="/route", tags=["routing"])


@router.post("/shortest")
def shortest_route(request: RouteRequest) -> dict:
    runtime = get_runtime()
    points = [request.start, *request.waypoints, request.end]
    node_ids = [runtime.graph.nearest_node_id(normalize_coordinate(point)) for point in points]
    if any(node_id is None for node_id in node_ids):
        raise HTTPException(404, "No routable road network loaded")

    avoid_polygons = [normalize_polygon(polygon) for polygon in request.avoid_polygons]
    excluded = edges_intersecting_polygons(runtime.roads, avoid_polygons) if avoid_polygons else set()
    segments: list[PathResult] = []
    for start_node, end_node in zip(node_ids, node_ids[1:]):
        if request.algorithm == "dijkstra":
            result = shortest_path(runtime.graph, start_node, end_node, request.mode, excluded)
        else:
            result = shortest_path_astar(runtime.graph, start_node, end_node, request.mode, excluded)
        if not result.found:
            raise HTTPException(404, "No route found")
        segments.append(result)

    geometry: list[tuple[float, float]] = []
    road_sequence: list[str] = []
    distance = 0.0
    estimated_time = 0.0
    for segment in segments:
        distance += segment.distance
        estimated_time += segment.estimated_time
        road_sequence.extend(segment.road_sequence)
        if not geometry:
            geometry.extend(segment.geometry)
        else:
            geometry.extend(segment.geometry[1:])

    return {
        "route_id": "route_001",
        "algorithm": request.algorithm,
        "mode": request.mode,
        "distance": distance,
        "estimated_time": estimated_time,
        "road_sequence": road_sequence,
        "geometry": {
            "type": "LineString",
            "coordinates": [[lon, lat] for lon, lat in geometry],
        },
        "excluded_edges": sorted(excluded),
    }

