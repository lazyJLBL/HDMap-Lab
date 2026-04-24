from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.geojson import normalize_polygon
from app.schemas import SpatialQueryRequest
from app.storage.runtime import get_runtime

router = APIRouter(prefix="/spatial", tags=["spatial-query"])


@router.post("/query")
def spatial_query(request: SpatialQueryRequest) -> dict:
    runtime = get_runtime()
    if request.query_type == "roads_in_bbox":
        if request.bbox is None:
            raise HTTPException(400, "roads_in_bbox requires bbox")
        roads = runtime.roads_in_bbox(tuple(request.bbox))
        return {
            "query_type": request.query_type,
            "count": len(roads),
            "roads": [road.id for road in roads],
        }
    if request.query_type == "points_in_polygon":
        if request.polygon is None:
            raise HTTPException(400, "points_in_polygon requires polygon")
        points = runtime.points_in_polygon(normalize_polygon(request.polygon), request.target)
        return {"query_type": request.query_type, "count": len(points), "points": points}
    if request.query_type == "roads_in_polygon":
        if request.polygon is None:
            raise HTTPException(400, "roads_in_polygon requires polygon")
        roads = runtime.roads_in_polygon(normalize_polygon(request.polygon))
        return {
            "query_type": request.query_type,
            "count": len(roads),
            "roads": [road.id for road in roads],
        }
    raise HTTPException(400, f"Unsupported query_type: {request.query_type}")

