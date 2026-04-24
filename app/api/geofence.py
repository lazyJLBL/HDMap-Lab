from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.geometry import point_in_polygon
from app.schemas import GeofenceCheckRequest
from app.storage.runtime import geofences_from_payload, get_runtime, trajectory_from_payload

router = APIRouter(prefix="/geofence", tags=["geofence"])


@router.post("/check")
def check_geofence(request: GeofenceCheckRequest) -> dict:
    runtime = get_runtime()
    if request.trajectory is not None:
        trajectory = trajectory_from_payload(request.trajectory.model_dump())
    else:
        trajectory = runtime.get_trajectory(request.trajectory_id)
    if trajectory is None:
        raise HTTPException(404, "Trajectory not found")

    geofences = (
        geofences_from_payload([item.model_dump() for item in request.geofences])
        if request.geofences is not None
        else runtime.geofences
    )
    events = []
    for geofence in geofences:
        previous_inside = False
        for index, point in enumerate(trajectory.points):
            relation = point_in_polygon(point.coordinate, geofence.coordinates)
            inside = relation in {"inside", "boundary"}
            if inside and not previous_inside:
                events.append(
                    {
                        "fence_id": geofence.id,
                        "fence_name": geofence.name,
                        "point_index": index,
                        "timestamp": point.timestamp,
                        "event": "enter",
                        "point": [point.lon, point.lat],
                    }
                )
            if previous_inside and not inside:
                events.append(
                    {
                        "fence_id": geofence.id,
                        "fence_name": geofence.name,
                        "point_index": index,
                        "timestamp": point.timestamp,
                        "event": "exit",
                        "point": [point.lon, point.lat],
                    }
                )
            previous_inside = inside
    return {"trajectory_id": trajectory.id, "entered": bool(events), "events": events}

