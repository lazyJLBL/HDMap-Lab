from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.response import ok
from app.core.geojson import normalize_coordinate, normalize_polygon
from app.routing.advanced import shortest_path_explained
from app.routing.constraints import edges_intersecting_polygons
from app.schemas import RouteExplainRequest
from app.storage.runtime import get_runtime

router = APIRouter(prefix="/routing", tags=["routing"])


@router.post("/explain")
def routing_explain(request: RouteExplainRequest) -> dict:
    runtime = get_runtime()
    start = runtime.graph.nearest_node_id(normalize_coordinate(request.start))
    end = runtime.graph.nearest_node_id(normalize_coordinate(request.end))
    if start is None or end is None:
        raise HTTPException(404, "No routable road network loaded")
    avoid_polygons = [normalize_polygon(polygon) for polygon in request.avoid_polygons]
    polygon_edges = edges_intersecting_polygons(runtime.roads, avoid_polygons) if avoid_polygons else set()
    excluded = polygon_edges if request.avoid_mode == "hard" else set()
    soft_avoid_edges = polygon_edges if request.avoid_mode == "soft" else set()
    preferred = request.prefer_road_classes or request.preferred_road_classes
    result = shortest_path_explained(
        runtime.graph,
        start,
        end,
        mode=request.mode,
        algorithm=request.algorithm,
        cost_mode=request.cost_mode,
        excluded_edges=excluded,
        preferred_road_classes=preferred,
        avoid_road_classes=request.avoid_road_classes,
        soft_avoid_edges=soft_avoid_edges,
        turn_cost_enabled=request.turn_cost,
        turn_penalty_seconds=request.turn_penalty_seconds,
        custom_weights=request.custom_weights,
        speed_profile=request.speed_profile,
    )
    if not result.found:
        raise HTTPException(404, "No route found")
    data = {
        "path": result.road_sequence,
        "road_sequence": result.road_sequence,
        "node_sequence": result.node_sequence,
        "total_distance_m": result.distance,
        "total_time_s": result.estimated_time,
        "edge_count": len(result.road_sequence),
        "turn_count": result.turn_count,
        "cost_breakdown": result.cost_breakdown,
        "total_cost": result.total_cost,
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in result.geometry]},
        "steps": [step.to_dict() for step in result.steps],
        "excluded_edges": sorted(excluded),
        "soft_avoid_edges": sorted(soft_avoid_edges),
        "visited_nodes": result.visited_nodes,
    }
    if request.return_debug_layers:
        data["debug_layers"] = result.debug_layers
    return ok(
        data,
        metrics=result.cost_breakdown,
        debug_layers=result.debug_layers if request.return_debug_layers else {},
    )
