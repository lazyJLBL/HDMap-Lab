from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import DatasetLoadRequest
from app.storage.runtime import get_runtime

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/load")
def load_dataset(request: DatasetLoadRequest) -> dict:
    runtime = get_runtime()
    try:
        if request.source == "sample":
            counts = runtime.load_sample()
        elif request.source == "geojson":
            if request.roads_geojson is not None:
                counts = runtime.load_geojson_payloads(
                    roads_geojson=request.roads_geojson,
                    trajectories_geojson=request.trajectories_geojson,
                    geofences_geojson=request.geofences_geojson,
                    pois_geojson=request.pois_geojson,
                )
            elif request.roads_path:
                counts = runtime.load_geojson_paths(
                    roads_path=request.roads_path,
                    trajectories_path=request.trajectories_path,
                    geofences_path=request.geofences_path,
                    pois_path=request.pois_path,
                )
            else:
                raise HTTPException(400, "geojson source requires roads_path or roads_geojson")
        elif request.source == "osm_file":
            if not request.osm_path:
                raise HTTPException(400, "osm_file source requires osm_path")
            counts = runtime.load_osm_path(request.osm_path)
        elif request.source == "osm_online":
            bbox = tuple(request.bbox) if request.bbox else None
            counts = runtime.load_osm_online(bbox=bbox, place=request.place)
        else:
            raise HTTPException(400, f"Unsupported source: {request.source}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"status": "loaded", "source": request.source, "counts": counts}

