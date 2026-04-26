from __future__ import annotations

import statistics
import time

from fastapi import APIRouter, HTTPException

from app.api.response import ok
from app.core.bbox import bbox_of_coords
from app.map_matching.evaluation import evaluate_case
from app.map_matching.synthetic import generate_low_frequency_case, generate_parallel_road_case
from app.schemas import MapMatchingBenchmarkRequest, SpatialIndexBenchmarkRequest
from app.spatial_index import BasicRTreeIndex, BruteForceIndex, GridIndex, QuadTreeIndex, STRRTreeIndex
from app.storage.runtime import get_runtime

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


@router.post("/spatial-index")
def spatial_index_benchmark(request: SpatialIndexBenchmarkRequest) -> dict:
    runtime = get_runtime()
    if not runtime.roads:
        raise HTTPException(404, "No roads loaded")
    items = [(bbox_of_coords(road.geometry), road.id) for road in runtime.roads]
    query = tuple(request.query_bbox) if request.query_bbox else runtime.visualization_state()["bounds"]
    if query is None:
        raise HTTPException(400, "No query bbox available")
    query_bbox = (query[0], query[1], query[2], query[3])
    rows = []
    for label, factory in [
        ("brute_force", lambda: BruteForceIndex(items)),
        ("grid", lambda: GridIndex(items)),
        ("quadtree", lambda: QuadTreeIndex(items)),
        ("rtree", lambda: BasicRTreeIndex(items)),
        ("str_rtree", lambda: STRRTreeIndex(items)),
    ]:
        build_started = time.perf_counter()
        index = factory()
        build_ms = (time.perf_counter() - build_started) * 1000.0
        latencies: list[float] = []
        count = 0
        for _ in range(request.iterations):
            started = time.perf_counter()
            result = index.query(query_bbox)
            latencies.append((time.perf_counter() - started) * 1000.0)
            count = len(result)
        rows.append(
            {
                "index": label,
                "build_ms": build_ms,
                "candidate_count": count,
                "p50_ms": statistics.median(latencies),
                "p95_ms": _percentile(latencies, 0.95),
                "p99_ms": _percentile(latencies, 0.99),
            }
        )
    return ok({"query_bbox": list(query_bbox), "results": rows}, metrics={"roads": len(runtime.roads)})


@router.post("/map-matching")
def map_matching_benchmark(request: MapMatchingBenchmarkRequest) -> dict:
    runtime = get_runtime()
    if runtime.candidate_searcher is None or len(runtime.roads) < 2:
        raise HTTPException(404, "No routable road network loaded")
    route = _sample_connected_route(runtime.roads)
    cases = [generate_parallel_road_case(route), generate_low_frequency_case(route)]
    results = [evaluate_case(case, runtime.candidate_searcher, runtime.graph, request.k) for case in cases]
    return ok({"cases": results}, metrics={"cases": len(results)})


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    index = min(len(values) - 1, max(0, round((len(values) - 1) * percentile)))
    return values[index]


def _sample_connected_route(roads):
    by_id = {road.id: road for road in roads}
    preferred = ["edge_h_01_11", "edge_h_11_21", "edge_v_21_22"]
    if all(road_id in by_id for road_id in preferred):
        return [by_id[road_id] for road_id in preferred]
    return roads[: min(3, len(roads))]
