from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models import RoadEdge, RoadNode
from app.routing.advanced import shortest_path_explained
from app.routing.constraints import edges_intersecting_polygons
from app.routing.graph_builder import RoadGraph
from app.routing.turn_cost import classify_turn, compute_turn_angle, restricted_turn, turn_penalty_seconds


def _node(node_id: str, lon: float, lat: float) -> RoadNode:
    return RoadNode(node_id, lon, lat)


def _edge(
    edge_id: str,
    start: RoadNode,
    end: RoadNode,
    length: float,
    *,
    oneway: bool = False,
    road_class: str = "local",
    turn_restrictions: list[dict] | None = None,
) -> RoadEdge:
    return RoadEdge(
        id=edge_id,
        from_node=start.id,
        to_node=end.id,
        geometry=[start.coordinate, end.coordinate],
        length=length,
        speed_limit=40.0,
        road_class=road_class,
        oneway=oneway,
        turn_restrictions=turn_restrictions,
    )


def _turn_graph() -> tuple[RoadGraph, dict[str, RoadNode], list[RoadEdge]]:
    nodes = {
        "a": _node("a", 0.0, 0.0),
        "b": _node("b", 0.001, 0.0),
        "c": _node("c", 0.001, 0.001),
    }
    roads = [
        _edge("ab", nodes["a"], nodes["b"], 100.0),
        _edge("bc", nodes["b"], nodes["c"], 100.0),
        _edge("ac", nodes["a"], nodes["c"], 260.0, road_class="primary"),
    ]
    return RoadGraph.build(list(nodes.values()), roads), nodes, roads


def test_oneway_blocks_reverse_route() -> None:
    a = _node("a", 0.0, 0.0)
    b = _node("b", 0.001, 0.0)
    graph = RoadGraph.build([a, b], [_edge("ab", a, b, 100.0, oneway=True)])

    assert shortest_path_explained(graph, "a", "b").found
    assert not shortest_path_explained(graph, "b", "a").found


def test_turn_restriction_blocks_forbidden_transition() -> None:
    a = _node("a", 0.0, 0.0)
    b = _node("b", 0.001, 0.0)
    c = _node("c", 0.001, 0.001)
    roads = [
        _edge("ab", a, b, 100.0, turn_restrictions=[{"from_edge": "ab", "to_edge": "bc", "type": "no_turn"}]),
        _edge("bc", b, c, 100.0),
    ]
    graph = RoadGraph.build([a, b, c], roads)
    previous = graph.adjacency["a"][0]
    current = next(arc for arc in graph.adjacency["b"] if arc.edge_id == "bc")

    assert restricted_turn(previous, current)
    assert not shortest_path_explained(graph, "a", "c").found


def test_turn_penalty_changes_path_choice() -> None:
    graph, _nodes, _roads = _turn_graph()

    no_turn_cost = shortest_path_explained(graph, "a", "c", algorithm="dijkstra", turn_cost_enabled=False)
    high_turn_cost = shortest_path_explained(
        graph,
        "a",
        "c",
        algorithm="dijkstra",
        turn_cost_enabled=True,
        turn_penalty_seconds=30.0,
    )

    assert no_turn_cost.road_sequence == ["ab", "bc"]
    assert high_turn_cost.road_sequence == ["ac"]
    assert high_turn_cost.cost_breakdown["turn_penalty"] == 0.0


def test_avoid_polygon_changes_path() -> None:
    graph, _nodes, roads = _turn_graph()
    avoid_polygon = [
        [
            (0.00045, 0.00040),
            (0.00060, 0.00040),
            (0.00060, 0.00060),
            (0.00045, 0.00060),
            (0.00045, 0.00040),
        ]
    ]
    excluded = edges_intersecting_polygons(roads, [avoid_polygon])

    assert "ac" in excluded
    result = shortest_path_explained(graph, "a", "c", excluded_edges=excluded, turn_cost_enabled=False)
    assert result.road_sequence == ["ab", "bc"]
    assert result.debug_layers["avoided_edges"]["type"] == "FeatureCollection"


def test_astar_and_dijkstra_return_same_cost_on_admissible_mode() -> None:
    graph, _nodes, _roads = _turn_graph()

    dijkstra = shortest_path_explained(graph, "a", "c", algorithm="dijkstra", turn_cost_enabled=False)
    astar = shortest_path_explained(graph, "a", "c", algorithm="astar", turn_cost_enabled=False)

    assert dijkstra.found and astar.found
    assert dijkstra.total_cost == astar.total_cost
    assert dijkstra.road_sequence == astar.road_sequence


def test_explain_steps_have_expected_fields() -> None:
    graph, _nodes, _roads = _turn_graph()

    result = shortest_path_explained(graph, "a", "c", algorithm="dijkstra")

    assert result.steps
    step = result.steps[0].to_dict()
    assert {"road_id", "instruction", "distance_m", "road_class", "cost", "cost_breakdown"} <= step.keys()
    assert {"distance", "travel_time", "turn_penalty", "avoid_penalty", "road_class_preference"} <= result.cost_breakdown.keys()
    assert result.debug_layers["route"]["type"] == "FeatureCollection"


def test_disconnected_graph_returns_not_found() -> None:
    a = _node("a", 0.0, 0.0)
    b = _node("b", 0.001, 0.0)
    c = _node("c", 0.01, 0.01)
    d = _node("d", 0.011, 0.01)
    graph = RoadGraph.build([a, b, c, d], [_edge("ab", a, b, 100.0), _edge("cd", c, d, 100.0)])

    assert not shortest_path_explained(graph, "a", "d").found


def test_turn_cost_helpers_classify_turns() -> None:
    graph, _nodes, _roads = _turn_graph()
    ab = graph.adjacency["a"][0]
    bc = next(arc for arc in graph.adjacency["b"] if arc.edge_id == "bc")

    angle = compute_turn_angle(ab, bc)
    assert classify_turn(angle) in {"left", "right"}
    assert turn_penalty_seconds(ab, bc, 10.0) > 0.0


def test_routing_explain_api_returns_debug_layers() -> None:
    client = TestClient(app)
    response = client.post(
        "/routing/explain",
        json={
            "start": [116.390, 39.900],
            "end": [116.410, 39.920],
            "mode": "shortest_distance",
            "algorithm": "astar",
            "cost_mode": "distance",
            "turn_cost": True,
            "return_debug_layers": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["path"]
    assert payload["data"]["steps"]
    assert payload["debug_layers"]["route"]["type"] == "FeatureCollection"
