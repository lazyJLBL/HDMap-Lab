from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.models import RoadEdge, RoadNode
from app.topology.validation import validate_topology


def road(
    road_id: str,
    coords: list[tuple[float, float]],
    *,
    from_node: str | None = None,
    to_node: str | None = None,
    road_class: str = "local",
    speed: float = 40.0,
    oneway: bool = False,
    direction: str | None = None,
    metadata: dict | None = None,
) -> RoadEdge:
    return RoadEdge(
        id=road_id,
        from_node=from_node or f"{road_id}_from",
        to_node=to_node or f"{road_id}_to",
        geometry=coords,
        length=100.0,
        speed_limit=speed,
        road_class=road_class,
        oneway=oneway,
        direction=direction or ("forward" if oneway else "both"),
        metadata=metadata or {},
    )


def nodes(*items: tuple[str, float, float]) -> list[RoadNode]:
    return [RoadNode(node_id, lon, lat) for node_id, lon, lat in items]


def nodes_from_roads(roads: list[RoadEdge], extra: list[RoadNode] | None = None) -> list[RoadNode]:
    result: dict[str, RoadNode] = {}
    for item in roads:
        result[item.from_node] = RoadNode(item.from_node, item.geometry[0][0], item.geometry[0][1])
        result[item.to_node] = RoadNode(item.to_node, item.geometry[-1][0], item.geometry[-1][1])
    for item in extra or []:
        result[item.id] = item
    return list(result.values())


def issue_types(report) -> set[str]:
    return {issue.type for issue in report.issues}


def test_crossing_without_node_issue() -> None:
    roads = [
        road("east_west", [(0, 0), (2, 0)], from_node="a", to_node="b"),
        road("north_south", [(1, -1), (1, 1)], from_node="c", to_node="d"),
    ]
    report = validate_topology(nodes_from_roads(roads), roads)

    assert "crossing_without_node" in issue_types(report)
    assert report.illegal_crossings[0].severity == "error"
    assert report.to_dict()["quality_score"] < 100


def test_overlapping_roads_issue() -> None:
    roads = [
        road("r1", [(0, 0), (3, 0)], from_node="a", to_node="b"),
        road("r2", [(1, 0), (4, 0)], from_node="c", to_node="d"),
    ]
    report = validate_topology(nodes_from_roads(roads), roads)

    assert "overlapping_roads" in issue_types(report)
    assert report.debug_layers["overlapping_roads"]["type"] == "FeatureCollection"


def test_dangling_and_isolated_nodes() -> None:
    roads = [road("stub", [(0, 0), (1, 0)], from_node="a", to_node="b")]
    report = validate_topology(nodes_from_roads(roads, nodes(("isolated", 9, 9))), roads)

    assert "dangling_edge" in issue_types(report)
    assert "isolated_node" in issue_types(report)
    assert "isolated" in report.isolated_nodes
    assert "stub" in report.dangling_edges


def test_self_intersection_and_zero_length_segment() -> None:
    roads = [
        road("bowtie", [(0, 0), (2, 2), (0, 2), (2, 0)], from_node="a", to_node="b"),
        road("zero", [(5, 5), (5, 5), (6, 5)], from_node="c", to_node="d"),
    ]
    report = validate_topology(nodes_from_roads(roads), roads)

    assert "self_intersecting_road" in issue_types(report)
    assert "zero_length_segment" in issue_types(report)
    assert "duplicated_points_in_road" in issue_types(report)


def test_invalid_metadata_issues() -> None:
    roads = [
        road(
            "bad_meta",
            [(0, 0), (1, 0)],
            from_node="a",
            to_node="b",
            road_class="",
            speed=200.0,
            oneway=True,
            direction="both",
            metadata={"layer": "bad", "bridge": True, "tunnel": True},
        )
    ]
    report = validate_topology(nodes_from_roads(roads), roads)

    assert {"invalid_speed", "missing_road_class", "invalid_layer", "inconsistent_bridge_tunnel_layer", "oneway_metadata_conflict"} <= issue_types(report)


def test_quality_score_decreases_with_more_issues() -> None:
    clean_roads = [
        road("ab", [(0, 0), (1, 0)], from_node="a", to_node="b"),
        road("bc", [(1, 0), (0.5, 1)], from_node="b", to_node="c"),
        road("ca", [(0.5, 1), (0, 0)], from_node="c", to_node="a"),
    ]
    dirty_roads = [
        *clean_roads,
        road("cross1", [(0, 0.2), (1, 0.8)], from_node="x1", to_node="x2", speed=180),
        road("cross2", [(0, 0.8), (1, 0.2)], from_node="y1", to_node="y2"),
    ]

    clean = validate_topology(nodes_from_roads(clean_roads), clean_roads)
    dirty = validate_topology(nodes_from_roads(dirty_roads), dirty_roads)

    assert dirty.quality_score < clean.quality_score


def test_debug_layers_are_geojson_serializable() -> None:
    roads = [
        road("r1", [(0, 0), (2, 0)], from_node="a", to_node="b"),
        road("r2", [(1, -1), (1, 1)], from_node="c", to_node="d"),
    ]
    report = validate_topology(nodes_from_roads(roads), roads)
    payload = report.to_dict()

    json.dumps(payload["debug_layers"])
    assert payload["debug_layers"]["crossing_without_node"]["type"] == "FeatureCollection"
    assert payload["metrics"]["node_count"] == 4
    assert payload["summary"]["quality_score"] == payload["quality_score"]


def test_topology_validate_api_returns_quality_score_and_debug_layers() -> None:
    client = TestClient(app)
    response = client.post(
        "/topology/validate",
        json={
            "detect_crossings": True,
            "detect_overlaps": True,
            "detect_near_miss": True,
            "near_miss_tolerance_m": 1.0,
            "respect_layers": True,
            "return_debug_layers": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "quality_score" in payload["data"]
    assert isinstance(payload["data"]["debug_layers"], dict)
