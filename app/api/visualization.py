from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.response import ok
from app.storage.runtime import get_runtime

router = APIRouter(prefix="/visualization", tags=["visualization"])


@router.get("/state")
def visualization_state() -> dict:
    return get_runtime().visualization_state()


@router.get("/export")
def visualization_export() -> dict:
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "format": "geojson-layer-bundle",
        "layers": get_runtime().visualization_state(),
    }


@router.get("/experiments")
def visualization_experiments() -> dict:
    runtime = get_runtime()
    state = runtime.visualization_state()
    return ok(
        {
            "experiments": [
                {
                    "id": "topology_repair",
                    "name": "Dirty Road Repair",
                    "layers": ["roads", "fixed_roads", "illegal_crossings", "dangling_edges"],
                },
                {
                    "id": "spatial_index",
                    "name": "Spatial Index Benchmark",
                    "layers": ["query_bbox", "candidate_roads"],
                },
                {
                    "id": "map_matching",
                    "name": "HMM Candidate/Viterbi",
                    "layers": ["trajectories", "candidate_points", "matched_path"],
                },
                {
                    "id": "trajectory_analysis",
                    "name": "Trajectory Error Heatmap",
                    "layers": ["trajectories", "deviation_points"],
                },
            ],
            "base_layers": state,
        },
        metrics={"roads": len(runtime.roads), "trajectories": len(runtime.trajectories)},
    )
