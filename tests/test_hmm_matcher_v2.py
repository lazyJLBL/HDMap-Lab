from __future__ import annotations

from app.geometry_kernel.polyline import polyline_length
from app.map_matching import match_hmm, match_nearest
from app.map_matching.candidate_search import CandidateSearcher
from app.map_matching.evaluation import evaluate_match_result
from app.map_matching.synthetic import generate_synthetic_case
from app.models import RoadEdge, RoadNode, Trajectory, TrajectoryPoint
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


def test_hmm_weight_overrides_change_reported_match_cost() -> None:
    nodes = [
        RoadNode("a", 116.000, 39.000),
        RoadNode("b", 116.010, 39.000),
        RoadNode("c", 116.000, 39.010),
    ]
    roads = [
        RoadEdge(
            id="east_residential",
            from_node="a",
            to_node="b",
            geometry=[nodes[0].coordinate, nodes[1].coordinate],
            length=polyline_length([nodes[0].coordinate, nodes[1].coordinate]),
            road_class="residential",
            road_type="residential",
        ),
        RoadEdge(
            id="north_primary",
            from_node="a",
            to_node="c",
            geometry=[nodes[0].coordinate, nodes[2].coordinate],
            length=polyline_length([nodes[0].coordinate, nodes[2].coordinate]),
            road_class="primary",
            road_type="primary",
        ),
    ]
    trajectory = Trajectory(
        "north_heading_on_east_road",
        [
            TrajectoryPoint(116.005, 39.000),
            TrajectoryPoint(116.005, 39.0001),
        ],
    )
    searcher = CandidateSearcher(roads)
    graph = RoadGraph.build(nodes, roads)

    no_heading = match_hmm(trajectory, searcher, graph, k=2, radius_m=1000.0, heading_weight=0.0)
    strong_heading = match_hmm(trajectory, searcher, graph, k=2, radius_m=1000.0, heading_weight=10.0)
    no_class = match_hmm(trajectory, searcher, graph, k=2, radius_m=1000.0, road_class_weight=0.0)
    strong_class = match_hmm(trajectory, searcher, graph, k=2, radius_m=1000.0, road_class_weight=10.0)

    assert strong_heading["matches"][0]["cost_breakdown"]["heading"] > no_heading["matches"][0]["cost_breakdown"]["heading"]
    assert strong_heading["metrics"]["dp_final_cost"] > no_heading["metrics"]["dp_final_cost"]
    assert strong_class["matches"][0]["cost_breakdown"]["road_class"] > no_class["matches"][0]["cost_breakdown"]["road_class"]
    assert strong_class["metrics"]["dp_final_cost"] > no_class["metrics"]["dp_final_cost"]
