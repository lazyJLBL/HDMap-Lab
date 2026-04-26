from __future__ import annotations

from app.models import RoadEdge, RoadNode
from app.topology import repair_topology, validate_topology


def test_topology_validation_and_repair_splits_crossing_and_removes_duplicate() -> None:
    nodes = [
        RoadNode("a", 0.0, 0.0),
        RoadNode("b", 2.0, 0.0),
        RoadNode("c", 1.0, -1.0),
        RoadNode("d", 1.0, 1.0),
        RoadNode("b_near", 2.00000001, 0.0),
    ]
    roads = [
        RoadEdge("horizontal", "a", "b", [(0.0, 0.0), (2.0, 0.0)], 2.0),
        RoadEdge("vertical", "c", "d", [(1.0, -1.0), (1.0, 1.0)], 2.0),
        RoadEdge("duplicate", "a", "b_near", [(0.0, 0.0), (2.00000001, 0.0)], 2.0),
    ]

    before = validate_topology(nodes, roads)
    repaired = repair_topology(nodes, roads, snap_tolerance_m=2.0)

    assert before.illegal_crossings
    assert repaired.operations["split_edges_added"] > 0
    assert repaired.operations["duplicate_edges_removed"] >= 1
    assert repaired.after.to_dict()["summary"]["illegal_crossings"] == 0
