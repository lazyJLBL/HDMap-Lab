from __future__ import annotations

from app.map_matching import match_hmm
from app.map_matching.candidate_search import CandidateSearcher
from app.map_matching.evaluation import edit_distance, evaluate_match_result, precision_recall_f1, sequence_accuracy
from app.map_matching.synthetic import generate_synthetic_case
from app.routing.graph_builder import RoadGraph


def test_basic_metric_functions() -> None:
    assert sequence_accuracy(["a", "b"], ["a", "c"]) == 0.5
    assert precision_recall_f1(["a", "b"], ["a", "c"]) == (0.5, 0.5, 0.5)
    assert edit_distance(["a", "b"], ["a", "c", "d"]) == 2


def test_evaluation_metrics_are_complete() -> None:
    case = generate_synthetic_case("straight_clean")
    searcher = CandidateSearcher(case.roads)
    graph = RoadGraph.build(case.nodes, case.roads)
    result = match_hmm(case.trajectory, searcher, graph, k=5)
    metrics = evaluate_match_result(result, case, latency_ms=1.2)

    assert {
        "sequence_accuracy",
        "precision",
        "recall",
        "f1",
        "edit_distance",
        "route_length_error",
        "matched_point_error_mean",
        "matched_point_error_p95",
        "continuity_score",
        "illegal_transition_count",
        "latency_ms",
        "candidate_count_avg",
    } <= set(metrics)
    assert metrics["latency_ms"] == 1.2
    assert metrics["candidate_count_avg"] > 0
