from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.response import ok
from app.core.geojson import normalize_coordinate
from app.schemas import TrajectoryAnalyzeRequest
from app.storage.runtime import get_runtime, trajectory_from_payload
from app.trajectory import analyze_trajectory

router = APIRouter(prefix="/trajectory", tags=["trajectory"])


@router.post("/analyze")
def trajectory_analyze(request: TrajectoryAnalyzeRequest) -> dict:
    runtime = get_runtime()
    if request.trajectory is not None:
        trajectory = trajectory_from_payload(request.trajectory.model_dump())
    else:
        trajectory = runtime.get_trajectory(request.trajectory_id)
    if trajectory is None:
        raise HTTPException(404, "Trajectory not found")
    reference = [normalize_coordinate(point) for point in request.reference] if request.reference else None
    data = analyze_trajectory(
        trajectory.coordinates,
        reference=reference,
        simplify_tolerance_m=request.simplify_tolerance_m,
        deviation_threshold_m=request.deviation_threshold_m,
    )
    return ok(data, metrics={"point_count": data["point_count"], "length_m": data["length_m"]})
