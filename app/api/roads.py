from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.storage.runtime import get_runtime

router = APIRouter(prefix="/roads", tags=["roads"])


@router.get("/nearby")
def nearby_roads(
    lon: float = Query(...),
    lat: float = Query(...),
    k: int = Query(5, ge=1, le=50),
) -> dict:
    runtime = get_runtime()
    if runtime.candidate_searcher is None:
        raise HTTPException(404, "No road network loaded")
    candidates = runtime.candidate_searcher.nearby_roads((lon, lat), k)
    return {"roads": [candidate.to_dict() for candidate in candidates]}

