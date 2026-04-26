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
    excluded = edges_intersecting_polygons(runtime.roads, avoid_polygons) if avoid_polygons else set()
    result = shortest_path_explained(
        runtime.graph,
        start,
        end,
        mode=request.mode,
        excluded_edges=excluded,
        preferred_road_classes=request.preferred_road_classes,
        turn_penalty_seconds=request.turn_penalty_seconds,
    )
    if not result.found:
        raise HTTPException(404, "No route found")
    return ok(
        {
            "road_sequence": result.road_sequence,
            "node_sequence": result.node_sequence,
            "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in result.geometry]},
            "steps": [step.to_dict() for step in result.steps],
            "excluded_edges": sorted(excluded),
        },
        metrics=result.cost_breakdown,
    )
