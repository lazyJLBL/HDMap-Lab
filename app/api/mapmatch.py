from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.map_matching import match_candidate_cost, match_hmm, match_nearest
from app.schemas import MapMatchRequest
from app.storage.runtime import get_runtime, trajectory_from_payload

router = APIRouter(tags=["map-matching"])


@router.post("/mapmatch")
def mapmatch(request: MapMatchRequest) -> dict:
    runtime = get_runtime()
    if runtime.candidate_searcher is None:
        raise HTTPException(404, "No road network loaded")
    if request.trajectory is not None:
        trajectory = trajectory_from_payload(request.trajectory.model_dump())
    else:
        trajectory = runtime.get_trajectory(request.trajectory_id)
    if trajectory is None:
        raise HTTPException(404, "Trajectory not found")

    if request.algorithm == "nearest":
        return match_nearest(trajectory, runtime.candidate_searcher, request.k)
    if request.algorithm == "candidate_cost":
        return match_candidate_cost(trajectory, runtime.candidate_searcher, runtime.graph, request.k)
    return match_hmm(
        trajectory,
        runtime.candidate_searcher,
        runtime.graph,
        k=request.k,
        sigma=request.sigma,
        beta=request.beta,
    )

