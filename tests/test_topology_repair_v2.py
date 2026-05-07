from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models import RoadEdge, RoadNode
from app.topology.repair import repair_topology


def road(
    road_id: str,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    from_node: str | None = None,
    to_node: str | None = None,
    road_class: str = "local",
    speed: float = 40.0,
    oneway: bool = False,
    metadata: dict | None = None,
    length: float | None = None,
) -> RoadEdge:
    return RoadEdge(
        id=road_id,
        from_node=from_node or f"{road_id}_from",
        to_node=to_node or f"{road_id}_to",
        geometry=[start, end],
        length=length if length is not None else 100.0,
        road_class=road_class,
        speed_limit=speed,
        oneway=oneway,
        direction="forward" if oneway else "both",
        metadata=metadata or {},
    )


def nodes_from_roads(roads: list[RoadEdge]) -> list[RoadNode]:
    nodes: dict[str, RoadNode] = {}
    for item in roads:
        nodes[item.from_node] = RoadNode(item.from_node, item.geometry[0][0], item.geometry[0][1])
        nodes[item.to_node] = RoadNode(item.to_node, item.geometry[-1][0], item.geometry[-1][1])
    return list(nodes.values())


def test_crossing_roads_are_split() -> None:
    roads = [
        road("east_west", (0, 0), (2, 0), from_node="a", to_node="b"),
        road("north_south", (1, -1), (1, 1), from_node="c", to_node="d"),
    ]
    result = repair_topology(nodes_from_roads(roads), roads, snap_tolerance_m=0.0)

    assert result.operations["split_edges_added"] == 2
    assert len(result.operations["split_events"]) == 2
    assert any(item["geometry"]["type"] == "Point" for item in result.debug_layers["split_points"]["features"])
    assert result.after.to_dict()["summary"]["illegal_crossings"] == 0


def test_endpoint_touch_is_not_split_again() -> None:
    roads = [
        road("left", (0, 0), (1, 0), from_node="a", to_node="b"),
        road("right", (1, 0), (2, 0), from_node="b", to_node="c"),
    ]
    result = repair_topology(nodes_from_roads(roads), roads, snap_tolerance_m=0.0)

    assert result.operations["split_edges_added"] == 0
    assert result.operations["split_events"] == []


def test_overpass_different_layer_is_not_split() -> None:
    roads = [
        road("surface", (0, 0), (2, 0), metadata={"layer": 0}),
        road("bridge", (1, -1), (1, 1), metadata={"layer": 1, "bridge": True}),
    ]
    result = repair_topology(nodes_from_roads(roads), roads, snap_tolerance_m=0.0, respect_layers=True)

    assert result.operations["split_edges_added"] == 0
    assert len(result.roads) == 2


def test_close_nodes_snap_but_different_layers_do_not_snap() -> None:
    same_layer_roads = [
        road("r1", (0, 0), (0.000001, 0), from_node="a", to_node="b", metadata={"layer": 0}),
        road("r2", (0.0000015, 0), (0.001, 0), from_node="b_near", to_node="c", metadata={"layer": 0}),
    ]
    snapped = repair_topology(nodes_from_roads(same_layer_roads), same_layer_roads, snap_tolerance_m=1.0)
    assert snapped.operations["snapped_nodes"] >= 1

    different_layer_roads = [
        road("r1", (0, 0), (0.000001, 0), from_node="a", to_node="b", metadata={"layer": 0}),
        road("r2", (0.0000015, 0), (0.001, 0), from_node="b_near", to_node="c", metadata={"layer": 1, "bridge": True}),
    ]
    not_snapped = repair_topology(nodes_from_roads(different_layer_roads), different_layer_roads, snap_tolerance_m=1.0)
    assert not_snapped.operations["snapped_nodes"] == 0


def test_same_direction_duplicate_removed_and_metadata_richer_edge_kept() -> None:
    roads = [
        road("plain", (0, 0), (1, 0), from_node="a", to_node="b", metadata={"layer": 0}),
        road("rich", (0, 0), (1, 0), from_node="a2", to_node="b2", metadata={"layer": 0, "name": "Main", "source": "fixture"}),
    ]
    result = repair_topology(nodes_from_roads(roads), roads, snap_tolerance_m=0.0)

    assert result.operations["duplicate_edges_removed"] == 1
    assert result.roads[0].id == "rich"
    assert result.operations["duplicate_groups"][0]["kept_road_id"] == "rich"


def test_reverse_oneway_pair_is_not_removed() -> None:
    roads = [
        road("forward", (0, 0), (1, 0), from_node="a", to_node="b", oneway=True),
        road("backward", (1, 0), (0, 0), from_node="b2", to_node="a2", oneway=True),
    ]
    result = repair_topology(nodes_from_roads(roads), roads, snap_tolerance_m=0.0)

    assert result.operations["duplicate_edges_removed"] == 0
    assert {item.id for item in result.roads} == {"forward", "backward"}


def test_collinear_roads_merge_when_middle_degree_is_two() -> None:
    roads = [
        road("ab", (0, 0), (1, 0), from_node="a", to_node="b", road_class="primary", speed=50.0),
        road("bc", (1, 0), (2, 0), from_node="b", to_node="c", road_class="primary", speed=50.0),
    ]
    result = repair_topology(nodes_from_roads(roads), roads, snap_tolerance_m=0.0, merge_collinear=True)

    assert result.operations["merged_collinear_roads"] == 1
    assert len(result.roads) == 1
    assert result.roads[0].geometry == [(0, 0), (1, 0), (2, 0)]


def test_dangling_edge_mark_or_remove_short() -> None:
    roads = [road("stub", (0, 0), (0.00001, 0), from_node="a", to_node="b", length=5.0)]
    marked = repair_topology(nodes_from_roads(roads), roads, snap_tolerance_m=0.0, dangling_mode="mark_only")
    assert marked.roads[0].metadata["dangling"] is True
    assert marked.operations["dangling_edges"][0]["action"] == "marked"

    removed = repair_topology(
        nodes_from_roads(roads),
        roads,
        snap_tolerance_m=0.0,
        dangling_mode="remove_short",
        dangling_length_threshold_m=10.0,
    )
    assert removed.roads == []
    assert removed.operations["dangling_edges_removed"] == 1


def test_repair_history_and_debug_layers_are_preserved() -> None:
    roads = [
        road("east_west", (0, 0), (2, 0), from_node="a", to_node="b", metadata={"road_class": "test"}),
        road("north_south", (1, -1), (1, 1), from_node="c", to_node="d"),
    ]
    result = repair_topology(nodes_from_roads(roads), roads, snap_tolerance_m=0.0)

    assert all(item.metadata and item.metadata["repair_history"] for item in result.roads)
    assert set(result.debug_layers) >= {
        "original_roads",
        "snapped_nodes",
        "split_points",
        "duplicate_edges",
        "merged_roads",
        "dangling_edges",
        "repaired_roads",
    }


def test_topology_repair_api_returns_debug_layers() -> None:
    client = TestClient(app)
    response = client.post(
        "/topology/repair",
        json={
            "snap_tolerance_m": 1.0,
            "split_intersections": True,
            "merge_collinear": False,
            "dangling_mode": "mark_only",
            "return_debug_layers": True,
            "apply": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "repaired_roads" in payload["debug_layers"]
    assert payload["data"]["debug_layers"]["repaired_roads"]["type"] == "FeatureCollection"
