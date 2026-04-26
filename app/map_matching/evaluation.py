from __future__ import annotations

import time

from app.map_matching import match_hmm, match_nearest
from app.map_matching.candidate_search import CandidateSearcher
from app.map_matching.synthetic import SyntheticCase
from app.routing.graph_builder import RoadGraph


def evaluate_case(case: SyntheticCase, searcher: CandidateSearcher, graph: RoadGraph, k: int = 5) -> dict:
    nearest = _timed(lambda: match_nearest(case.trajectory, searcher, k))
    hmm = _timed(lambda: match_hmm(case.trajectory, searcher, graph, k=k))
    return {
        "case": case.name,
        "description": case.description,
        "ground_truth": case.ground_truth_roads,
        "nearest": _score_result(nearest["result"], case.ground_truth_roads) | {"latency_ms": nearest["latency_ms"]},
        "hmm": _score_result(hmm["result"], case.ground_truth_roads) | {"latency_ms": hmm["latency_ms"]},
    }


def _timed(func) -> dict:
    started = time.perf_counter()
    result = func()
    return {"result": result, "latency_ms": (time.perf_counter() - started) * 1000.0}


def _score_result(result: dict, ground_truth: list[str]) -> dict:
    predicted = result.get("matched_road_sequence", [])
    truth = _dedupe(ground_truth)
    hits = sum(1 for road_id in predicted if road_id in truth)
    precision = hits / len(predicted) if predicted else 0.0
    recall = hits / len(truth) if truth else 0.0
    exact = predicted == truth
    return {
        "sequence": predicted,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "exact_match": exact,
        "confidence": result.get("confidence", 0.0),
    }


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if not result or result[-1] != item:
            result.append(item)
    return result
