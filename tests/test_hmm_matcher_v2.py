from __future__ import annotations

from app.map_matching import match_hmm, match_nearest
from app.map_matching.candidate_search import CandidateSearcher
from app.map_matching.evaluation import evaluate_match_result
from app.map_matching.synthetic import generate_synthetic_case
from app.routing.graph_builder import RoadGraph


def test_parallel_roads_nearest_wrong_hmm_better() -> None:
    case = generate_synthetic_case("parallel_roads_drift")
    searcher = CandidateSearcher(case.roads)
    graph = RoadGraph.build(case.nodes, case.roads)
    nearest = match_nearest(case.trajectory, searcher, k=5)
    hmm = match_hmm(case.trajectory, searcher, graph, k=5, beam_width=3)

    nearest_metrics = evaluate_match_result(nearest, case)
    hmm_metrics = evaluate_match_result(hmm, case)
    assert nearest_metrics["sequence_accuracy"] < hmm_metrics["sequence_accuracy"]
    assert hmm["confidence"] > 0
    assert hmm["matches"][0]["cost_breakdown"]["emission"] >= 0


def test_low_frequency_case_returns_debug_layers() -> None:
    case = generate_synthetic_case("low_frequency_sampling")
    searcher = CandidateSearcher(case.roads)
    graph = RoadGraph.build(case.nodes, case.roads)
    result = match_hmm(case.trajectory, searcher, graph, k=5)

    assert result["matches"]
    assert result["debug_layers"]["gps_points"]["type"] == "FeatureCollection"
    assert result["metrics"]["candidate_count_avg"] > 0


def test_candidate_empty_fallback() -> None:
    class EmptySearcher:
        def search(self, *args, **kwargs):
            return []

    case = generate_synthetic_case("straight_clean")
    graph = RoadGraph.build(case.nodes, case.roads)
    result = match_hmm(case.trajectory, EmptySearcher(), graph, k=5)  # type: ignore[arg-type]

    assert result["algorithm"] == "hmm"
    assert result["confidence"] == 0.0
    assert result["metrics"]["candidate_empty_fallback"] is True


def test_overpass_layer_consistency_candidate_present() -> None:
    case = generate_synthetic_case("overpass_layer_confusion")
    searcher = CandidateSearcher(case.roads)
    graph = RoadGraph.build(case.nodes, case.roads)
    result = match_hmm(case.trajectory, searcher, graph, k=8)

    all_candidate_layers = {candidate["layer"] for layer in result["candidates"] for candidate in layer}
    assert {0, 1} <= all_candidate_layers
