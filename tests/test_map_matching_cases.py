from __future__ import annotations

from app.map_matching import match_hmm, match_nearest
from app.map_matching.candidate_search import CandidateSearcher
from app.map_matching.cost_model import cost_breakdown, trajectory_heading
from app.map_matching.evaluation import evaluate_match_result
from app.map_matching.synthetic import generate_synthetic_case
from app.routing.graph_builder import RoadGraph


def _run_case(case_id: str):
    case = generate_synthetic_case(case_id)
    case.roads = [road for road in case.roads if road.id != "oneway_forward"]
    searcher = CandidateSearcher(case.roads)
    graph = RoadGraph.build(case.nodes, case.roads)
    nearest = match_nearest(case.trajectory, searcher, k=5)
    hmm = match_hmm(case.trajectory, searcher, graph, k=5, radius_m=150.0)
    return case, searcher, graph, nearest, hmm


def test_nearest_matching_returns_projection_for_each_clean_point() -> None:
    case, _searcher, _graph, nearest, _hmm = _run_case("straight_clean")

    assert nearest["algorithm"] == "nearest"
    assert len(nearest["matches"]) == len(case.trajectory.points)
    assert all(match["projection_point"] for match in nearest["matches"])
    assert set(nearest["matched_road_sequence"]) <= {"main_0", "main_1"}


def test_hmm_matching_returns_debug_layers_and_cost_breakdown() -> None:
    case, _searcher, _graph, _nearest, hmm = _run_case("low_frequency_sampling")

    metrics = evaluate_match_result(hmm, case)

    assert hmm["algorithm"] == "hmm"
    assert hmm["matched_road_sequence"] == ["main_0", "main_1"]
    assert metrics["f1"] == 1.0
    assert hmm["debug_layers"]["matched_points"]["type"] == "FeatureCollection"
    assert hmm["matches"][0]["cost_breakdown"]["total"] >= 0.0


def test_parallel_road_drift_hmm_outperforms_nearest() -> None:
    case, _searcher, _graph, nearest, hmm = _run_case("parallel_roads_drift")

    nearest_metrics = evaluate_match_result(nearest, case)
    hmm_metrics = evaluate_match_result(hmm, case)

    assert "parallel_service" in nearest["matched_road_sequence"]
    assert hmm_metrics["f1"] > nearest_metrics["f1"]
    assert hmm_metrics["illegal_transition_count"] == 0


def test_sparse_gps_points_still_preserve_route_sequence() -> None:
    case, _searcher, _graph, nearest, hmm = _run_case("low_frequency_sampling")

    nearest_metrics = evaluate_match_result(nearest, case)
    hmm_metrics = evaluate_match_result(hmm, case)

    assert len(case.trajectory.points) == 4
    assert hmm["matched_road_sequence"] == ["main_0", "main_1"]
    assert hmm_metrics["edit_distance"] < nearest_metrics["edit_distance"]


def test_one_way_violation_is_penalized_in_candidate_cost() -> None:
    case = generate_synthetic_case("one_way_violation_case")
    searcher = CandidateSearcher(case.roads)
    graph = RoadGraph.build(case.nodes, case.roads)
    heading = (trajectory_heading(case.trajectory, 0) + 180.0) % 360.0
    candidates = searcher.search(case.trajectory.points[0].coordinate, k=8, heading=heading)
    oneway_candidate = next(candidate for candidate in candidates if candidate.road.id == "oneway_forward")
    breakdown = cost_breakdown(graph, oneway_candidate, heading)

    assert oneway_candidate.road.oneway
    assert not oneway_candidate.is_oneway_compatible
    assert breakdown["oneway"] == 25.0


def test_noisy_gps_hmm_keeps_core_roads_without_illegal_transitions() -> None:
    case, _searcher, _graph, nearest, hmm = _run_case("gps_outliers")

    nearest_metrics = evaluate_match_result(nearest, case)
    hmm_metrics = evaluate_match_result(hmm, case)

    assert set(hmm["matched_road_sequence"]) == {"main_0", "main_1"}
    assert hmm_metrics["f1"] >= nearest_metrics["f1"]
    assert hmm_metrics["illegal_transition_count"] == 0
