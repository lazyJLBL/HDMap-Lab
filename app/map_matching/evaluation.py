from __future__ import annotations

import time
from typing import Callable

from app.geometry_kernel.polyline import polyline_length
from app.map_matching import match_hmm, match_nearest
from app.map_matching.candidate_search import CandidateSearcher
from app.map_matching.synthetic import SyntheticCase
from app.routing.graph_builder import RoadGraph


def evaluate_case(case: SyntheticCase, searcher: CandidateSearcher, graph: RoadGraph, k: int = 5) -> dict:
    nearest = _timed(lambda: match_nearest(case.trajectory, searcher, k))
    hmm = _timed(lambda: match_hmm(case.trajectory, searcher, graph, k=k))
    return {
        "case": case.name,
        "case_id": case.case_id,
        "description": case.description,
        "ground_truth": _dedupe(case.ground_truth_roads),
        "nearest": evaluate_match_result(nearest["result"], case, latency_ms=nearest["latency_ms"]),
        "hmm": evaluate_match_result(hmm["result"], case, latency_ms=hmm["latency_ms"]),
    }


def evaluate_match_result(result: dict, case: SyntheticCase, latency_ms: float = 0.0) -> dict:
    predicted = result.get("matched_road_sequence", [])
    truth = _dedupe(case.ground_truth_roads)
    point_truth = case.ground_truth_roads[: len(result.get("matches", []))]
    point_pred = [match.get("matched_road_id") for match in result.get("matches", [])]
    residuals = [float(match.get("distance_m", match.get("distance", 0.0))) for match in result.get("matches", [])]
    precision, recall, f1 = precision_recall_f1(predicted, truth)
    return {
        "sequence": predicted,
        "sequence_accuracy": sequence_accuracy(point_pred, point_truth),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "edit_distance": edit_distance(predicted, truth),
        "route_length_error": route_length_error(predicted, truth, case),
        "matched_point_error_mean": sum(residuals) / len(residuals) if residuals else 0.0,
        "matched_point_error_p95": _percentile(residuals, 0.95),
        "continuity_score": continuity_score(point_pred),
        "illegal_transition_count": illegal_transition_count(point_pred, case.roads),
        "latency_ms": latency_ms,
        "candidate_count_avg": result.get("metrics", {}).get("candidate_count_avg", _candidate_count_avg(result)),
        "confidence": result.get("confidence", 0.0),
    }


def sequence_accuracy(predicted: list[str | None], truth: list[str]) -> float:
    if not truth:
        return 1.0
    total = min(len(predicted), len(truth))
    if total == 0:
        return 0.0
    return sum(1 for left, right in zip(predicted, truth, strict=False) if left == right) / total


def precision_recall_f1(predicted: list[str], truth: list[str]) -> tuple[float, float, float]:
    predicted_set = set(predicted)
    truth_set = set(truth)
    hits = len(predicted_set & truth_set)
    precision = hits / len(predicted_set) if predicted_set else 0.0
    recall = hits / len(truth_set) if truth_set else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return round(precision, 4), round(recall, 4), round(f1, 4)


def edit_distance(left: list[str], right: list[str]) -> int:
    dp = [[0] * (len(right) + 1) for _ in range(len(left) + 1)]
    for i in range(len(left) + 1):
        dp[i][0] = i
    for j in range(len(right) + 1):
        dp[0][j] = j
    for i, left_item in enumerate(left, start=1):
        for j, right_item in enumerate(right, start=1):
            cost = 0 if left_item == right_item else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    return dp[-1][-1]


def route_length_error(predicted: list[str], truth: list[str], case: SyntheticCase) -> float:
    road_by_id = {road.id: road for road in case.roads}
    predicted_length = sum(polyline_length(road_by_id[road_id].geometry) for road_id in predicted if road_id in road_by_id)
    truth_length = sum(polyline_length(road_by_id[road_id].geometry) for road_id in truth if road_id in road_by_id)
    if truth_length <= 0:
        return 0.0
    return abs(predicted_length - truth_length) / truth_length


def continuity_score(sequence: list[str | None]) -> float:
    filtered = [item for item in sequence if item]
    if len(filtered) <= 1:
        return 1.0 if filtered else 0.0
    transitions = sum(1 for prev, curr in zip(filtered, filtered[1:], strict=False) if prev != curr)
    return max(0.0, 1.0 - transitions / (len(filtered) - 1))


def illegal_transition_count(sequence: list[str | None], roads) -> int:
    roads_by_id = {road.id: road for road in roads}
    illegal = 0
    filtered = [item for item in sequence if item]
    for prev, curr in zip(filtered, filtered[1:], strict=False):
        if prev == curr:
            continue
        prev_road = roads_by_id.get(prev)
        curr_road = roads_by_id.get(curr)
        if prev_road is None or curr_road is None:
            illegal += 1
            continue
        endpoints_prev = {prev_road.from_node, prev_road.to_node}
        endpoints_curr = {curr_road.from_node, curr_road.to_node}
        if not (endpoints_prev & endpoints_curr):
            illegal += 1
    return illegal


def _timed(func: Callable[[], dict]) -> dict:
    started = time.perf_counter()
    result = func()
    return {"result": result, "latency_ms": (time.perf_counter() - started) * 1000.0}


def _candidate_count_avg(result: dict) -> float:
    matches = result.get("matches", [])
    if not matches:
        return 0.0
    return sum(int(match.get("candidate_count", 0)) for match in matches) / len(matches)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    index = min(len(values) - 1, max(0, round((len(values) - 1) * percentile)))
    return values[index]


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if not result or result[-1] != item:
            result.append(item)
    return result
