from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import RoadEdge, RoadNode
from app.topology import repair_topology


def make_dirty_network() -> tuple[list[RoadNode], list[RoadEdge]]:
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
    return nodes, roads


def main() -> None:
    nodes, roads = make_dirty_network()
    started = time.perf_counter()
    result = repair_topology(nodes, roads, snap_tolerance_m=2.0)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    print("| Metric | Value |")
    print("| --- | ---: |")
    print(f"| elapsed_ms | {elapsed_ms:.3f} |")
    for key, value in result.operations.items():
        print(f"| {key} | {value} |")
    for key, value in result.after.to_dict()["summary"].items():
        print(f"| after_{key} | {value} |")


if __name__ == "__main__":
    main()
