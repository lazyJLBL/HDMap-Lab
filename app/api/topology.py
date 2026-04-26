from __future__ import annotations

from fastapi import APIRouter

from app.api.response import ok
from app.schemas import TopologyRequest
from app.storage.runtime import get_runtime
from app.topology import repair_topology, validate_topology

router = APIRouter(prefix="/topology", tags=["topology"])


@router.post("/validate")
def topology_validate() -> dict:
    runtime = get_runtime()
    report = validate_topology(runtime.nodes, runtime.roads)
    return ok(report.to_dict(), metrics=report.to_dict()["summary"])


@router.post("/repair")
def topology_repair(request: TopologyRequest) -> dict:
    runtime = get_runtime()
    result = repair_topology(runtime.nodes, runtime.roads, request.snap_tolerance_m)
    if request.apply:
        runtime.replace_network(result.nodes, result.roads)
    payload = result.to_dict()
    return ok(
        payload,
        metrics=payload["after"]["summary"] | result.operations,
        debug_layers={"fixed_roads": payload["fixed_roads"]},
    )
