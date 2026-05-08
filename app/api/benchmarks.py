from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from app.api.response import ok
from app.map_matching import match_hmm, match_nearest
from app.map_matching.candidate_search import CandidateSearcher
from app.map_matching.cost_model import HMMCostWeights
from app.map_matching.evaluation import evaluate_match_result
from app.map_matching.synthetic import generate_synthetic_case
from app.routing.graph_builder import RoadGraph
from app.schemas import MapMatchingBenchmarkRequest, SpatialIndexBenchmarkRequest
from app.storage.runtime import get_runtime
from benchmarks.spatial_index_benchmark import run_spatial_index_benchmark

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


@router.post("/spatial-index")
def spatial_index_benchmark(request: SpatialIndexBenchmarkRequest) -> dict:
    runtime = get_runtime()
    if not runtime.roads:
        raise HTTPException(404, "No roads loaded")
    query_types = request.query_types or ["bbox"]
    index_types = request.index_types or ["brute", "grid", "quadtree", "rtree", "str_rtree"]
    payload = run_spatial_index_benchmark(
        dataset=request.dataset,
        item_count=min(request.items, len(runtime.roads)),
        query_count=request.query_count if request.query_bbox is None else request.iterations,
        index_types=index_types,
        query_types=query_types,
        seed=request.seed,
        radius_m=request.radius_m,
        bbox_size_m=request.bbox_size_m,
        roads=runtime.roads[: request.items],
        bbox_queries=[tuple(request.query_bbox)] * request.iterations if request.query_bbox is not None else None,
        return_debug_layers=request.return_debug_layers,
    )
    if request.query_bbox is not None:
        payload["query_bbox"] = request.query_bbox
    return ok(
        {"results": payload["results"], "dataset": payload["dataset"], "debug_layers": payload["debug_layers"]},
        metrics={"roads": payload["item_count"], "query_count": payload["query_count"]},
        debug_layers=payload["debug_layers"],
    )


@router.post("/map-matching")
def map_matching_benchmark(request: MapMatchingBenchmarkRequest) -> dict:
    results = []
    debug_layers = {}
    for case_id in request.cases:
        case = generate_synthetic_case(case_id, noise_sigma_m=request.noise_sigma_m, sampling_interval=request.sampling_interval)
        searcher = CandidateSearcher(case.roads)
        graph = RoadGraph.build(case.nodes, case.roads)
        row = {"case": case.case_id, "description": case.description, "ground_truth": case.ground_truth_road_sequence}
        if "nearest" in request.algorithms:
            started = time.perf_counter()
            nearest = match_nearest(case.trajectory, searcher, request.k)
            row["nearest"] = evaluate_match_result(nearest, case, latency_ms=(time.perf_counter() - started) * 1000.0)
        if "hmm" in request.algorithms:
            started = time.perf_counter()
            hmm = match_hmm(
                case.trajectory,
                searcher,
                graph,
                k=request.k,
                sigma=request.sigma,
                beta=request.beta,
                radius_m=request.radius_m,
                cost_weights=HMMCostWeights(
                    emission_weight=request.emission_weight,
                    transition_weight=request.transition_weight,
                    heading_weight=request.heading_weight,
                    turn_weight=request.turn_weight,
                    road_class_weight=request.road_class_weight,
                    oneway_weight=request.oneway_weight,
                    layer_weight=request.layer_weight,
                    speed_weight=request.speed_weight,
                ),
            )
            row["hmm"] = evaluate_match_result(hmm, case, latency_ms=(time.perf_counter() - started) * 1000.0)
        results.append(row)
        if request.return_debug_layers:
            debug_layers[case.case_id] = case.debug_layers
    return ok({"cases": results}, metrics={"cases": len(results)}, debug_layers=debug_layers)


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
