from __future__ import annotations

from collections import Counter

from app.geometry_kernel.polyline import haversine_distance
from app.models import RoadEdge, RoadNode
from app.topology import repair_topology, validate_topology


def _road(
    road_id: str,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    from_node: str,
    to_node: str,
    length: float = 100.0,
) -> RoadEdge:
    return RoadEdge(
        id=road_id,
        from_node=from_node,
        to_node=to_node,
        geometry=[start, end],
        length=length,
        road_class="local",
    )


def _nodes_from_roads(roads: list[RoadEdge]) -> list[RoadNode]:
    nodes: dict[str, RoadNode] = {}
    for road in roads:
        nodes[road.from_node] = RoadNode(road.from_node, road.geometry[0][0], road.geometry[0][1])
        nodes[road.to_node] = RoadNode(road.to_node, road.geometry[-1][0], road.geometry[-1][1])
    return list(nodes.values())


def _issue_counts(report) -> Counter[str]:
    return Counter(issue.type for issue in report.issues)


def test_duplicated_edge_is_detected_and_removed() -> None:
    roads = [
        _road("main", (0.0, 0.0), (1.0, 0.0), from_node="a", to_node="b"),
        _road("main_copy", (0.0, 0.0), (1.0, 0.0), from_node="a2", to_node="b2"),
    ]
    nodes = _nodes_from_roads(roads)

    before = validate_topology(nodes, roads)
    repaired = repair_topology(nodes, roads, snap_tolerance_m=0.0)

    assert before.to_dict()["summary"]["duplicate_edges"] == 1
    assert repaired.operations["duplicate_edges_removed"] == 1
    assert repaired.after.to_dict()["summary"]["duplicate_edges"] == 0


def test_illegal_crossing_is_split_by_repair() -> None:
    roads = [
        _road("east_west", (0.0, 0.0), (2.0, 0.0), from_node="w", to_node="e"),
        _road("south_north", (1.0, -1.0), (1.0, 1.0), from_node="s", to_node="n"),
    ]
    nodes = _nodes_from_roads(roads)

    before = validate_topology(nodes, roads)
    repaired = repair_topology(nodes, roads, snap_tolerance_m=0.0)

    assert before.to_dict()["summary"]["illegal_crossings"] == 1
    assert repaired.operations["split_edges_added"] == 2
    assert repaired.after.to_dict()["summary"]["illegal_crossings"] == 0


def test_dangling_edge_can_be_removed_when_it_is_short() -> None:
    roads = [_road("short_stub", (0.0, 0.0), (0.00001, 0.0), from_node="a", to_node="b", length=5.0)]
    nodes = _nodes_from_roads(roads)

    before = validate_topology(nodes, roads)
    repaired = repair_topology(
        nodes,
        roads,
        snap_tolerance_m=0.0,
        dangling_mode="remove_short",
        dangling_length_threshold_m=10.0,
    )

    assert before.to_dict()["summary"]["dangling_edges"] == 1
    assert repaired.operations["dangling_edges_removed"] == 1
    assert repaired.roads == []


def test_close_but_unsnapped_nodes_are_detected_and_snapped() -> None:
    roads = [
        _road("left", (0.0, 0.0), (0.001, 0.0), from_node="a", to_node="b"),
        _road("right", (0.0010005, 0.0), (0.002, 0.0), from_node="c", to_node="d"),
    ]
    nodes = _nodes_from_roads(roads)

    distance_before = haversine_distance((0.001, 0.0), (0.0010005, 0.0))
    repaired = repair_topology(nodes, roads, snap_tolerance_m=1.0)

    snapped_cluster = next(
        cluster
        for cluster in repaired.operations["snap_report"]["clusters"]
        if {"b", "c"} <= set(cluster["node_ids"])
    )
    assert 0.0 < distance_before < 1.0
    assert repaired.operations["snapped_nodes"] >= 1
    assert snapped_cluster["size"] == 2


def test_disconnected_components_are_reported() -> None:
    roads = [
        _road("component_a", (0.0, 0.0), (1.0, 0.0), from_node="a0", to_node="a1"),
        _road("component_b", (10.0, 0.0), (11.0, 0.0), from_node="b0", to_node="b1"),
    ]

    report = validate_topology(_nodes_from_roads(roads), roads)

    assert report.to_dict()["summary"]["connected_components"] == 2
    assert report.components == [["a0", "a1"], ["b0", "b1"]]


def test_overlapping_roads_are_reported_separately_from_duplicates() -> None:
    roads = [
        _road("long", (0.0, 0.0), (3.0, 0.0), from_node="a", to_node="b"),
        _road("overlap", (1.0, 0.0), (2.0, 0.0), from_node="c", to_node="d"),
    ]

    report = validate_topology(_nodes_from_roads(roads), roads)
    counts = _issue_counts(report)

    assert counts["overlapping_roads"] == 1
    assert report.to_dict()["summary"]["duplicate_edges"] == 0


def test_repair_reduces_blocking_topology_issue_types() -> None:
    roads = [
        _road("main", (0.0, 0.0), (2.0, 0.0), from_node="a", to_node="b"),
        _road("cross", (1.0, -1.0), (1.0, 1.0), from_node="c", to_node="d"),
        _road("main_duplicate", (0.0, 0.0), (2.0, 0.0), from_node="a2", to_node="b2"),
    ]
    nodes = _nodes_from_roads(roads)

    repaired = repair_topology(nodes, roads, snap_tolerance_m=0.0)
    before_counts = _issue_counts(repaired.before)
    after_counts = _issue_counts(repaired.after)

    assert before_counts["duplicate_edge"] >= 1
    assert before_counts["crossing_without_node"] >= 1
    assert after_counts["duplicate_edge"] == 0
    assert after_counts["crossing_without_node"] == 0
    assert repaired.after.quality_score > repaired.before.quality_score
