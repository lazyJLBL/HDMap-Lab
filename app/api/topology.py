from __future__ import annotations

from fastapi import APIRouter

from app.api.response import ok
from app.schemas import TopologyRequest, TopologyValidateRequest
from app.storage.runtime import get_runtime
from app.topology import repair_topology, validate_topology

router = APIRouter(prefix="/topology", tags=["topology"])


@router.post("/validate")
def topology_validate(request: TopologyValidateRequest | None = None) -> dict:
    request = request or TopologyValidateRequest()
    runtime = get_runtime()
    report = validate_topology(
        runtime.nodes,
        runtime.roads,
        detect_crossings=request.detect_crossings,
        detect_overlaps=request.detect_overlaps,
        detect_near_miss=request.detect_near_miss,
        near_miss_tolerance_m=request.near_miss_tolerance_m,
        respect_layers=request.respect_layers,
        return_debug_layers=request.return_debug_layers,
    )
    return ok(report.to_dict(), metrics=report.to_dict()["summary"], debug_layers=report.debug_layers)


@router.post("/repair")
def topology_repair(request: TopologyRequest) -> dict:
    runtime = get_runtime()
    result = repair_topology(
        runtime.nodes,
        runtime.roads,
        snap_tolerance_m=request.snap_tolerance_m,
        split_intersections=request.split_intersections,
        merge_collinear=request.merge_collinear,
        dangling_mode=request.dangling_mode,
        dangling_length_threshold_m=request.dangling_length_threshold_m,
        respect_layers=request.respect_layers,
        preserve_metadata=request.preserve_metadata,
        return_debug_layers=request.return_debug_layers,
    )
    if request.apply:
        runtime.replace_network(result.nodes, result.roads)
    payload = result.to_dict()
    return ok(
        payload,
        metrics=payload["after"]["summary"] | result.operations,
        debug_layers=result.debug_layers or {"fixed_roads": payload["fixed_roads"]},
    )
