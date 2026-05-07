from __future__ import annotations

from app.map_matching.candidate_search import CandidateSearcher
from app.map_matching.cost_model import cost_breakdown, direction_cost, speed_feasibility_penalty, trajectory_heading
from app.map_matching.synthetic import generate_synthetic_case
from app.routing.graph_builder import RoadGraph


def test_cost_breakdown_fields_are_complete() -> None:
    case = generate_synthetic_case("parallel_roads_drift")
    searcher = CandidateSearcher(case.roads)
    graph = RoadGraph.build(case.nodes, case.roads)
    candidate = searcher.search(case.trajectory.points[0].coordinate, k=3)[0]
    breakdown = cost_breakdown(graph, candidate, trajectory_heading(case.trajectory, 0), sigma=20.0, beta=50.0)

    assert set(breakdown) == {"emission", "transition", "heading", "speed", "turn", "road_class", "oneway", "layer"}
    assert breakdown["emission"] >= 0


def test_one_way_penalty_and_heading_cost() -> None:
    case = generate_synthetic_case("one_way_violation_case")
    searcher = CandidateSearcher(case.roads)
    graph = RoadGraph.build(case.nodes, case.roads)
    candidate = next(item for item in searcher.search(case.trajectory.points[0].coordinate, k=10) if item.road.id == "oneway_forward")

    compatible = cost_breakdown(graph, candidate, candidate.road_heading)
    candidate.is_oneway_compatible = False
    incompatible = cost_breakdown(graph, candidate, (candidate.road_heading + 180.0) % 360.0)

    assert direction_cost(candidate, (candidate.road_heading + 180.0) % 360.0) > 0.9
    assert incompatible["oneway"] > compatible["oneway"]


def test_layer_consistency_and_speed_penalty() -> None:
    case = generate_synthetic_case("overpass_layer_confusion")
    searcher = CandidateSearcher(case.roads)
    graph = RoadGraph.build(case.nodes, case.roads)
    point = case.trajectory.points[2].coordinate
    candidates = searcher.search(point, k=10)
    surface = next(item for item in candidates if item.layer == 0)
    bridge = next(item for item in candidates if item.layer == 1)

    breakdown = cost_breakdown(graph, bridge, None, previous=surface, gps_distance=5.0, step_seconds=1.0)
    assert breakdown["layer"] > 0
    assert speed_feasibility_penalty(surface, bridge, gps_distance=100.0, step_seconds=1.0) > 0
