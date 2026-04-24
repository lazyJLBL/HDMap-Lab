from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.routing.astar import shortest_path_astar
from app.routing.dijkstra import shortest_path
from app.storage.runtime import RuntimeState


def timed(label: str, func):
    started = time.perf_counter()
    result = func()
    elapsed_ms = (time.perf_counter() - started) * 1000
    return label, elapsed_ms, result.distance, len(result.road_sequence)


def main() -> None:
    runtime = RuntimeState("data/benchmark.sqlite")
    runtime.load_sample()
    start = runtime.graph.nearest_node_id((116.390, 39.900))
    end = runtime.graph.nearest_node_id((116.410, 39.920))
    if start is None or end is None:
        raise RuntimeError("sample graph is missing")

    rows = [
        timed("Dijkstra shortest_distance", lambda: shortest_path(runtime.graph, start, end, "shortest_distance")),
        timed("A* shortest_distance", lambda: shortest_path_astar(runtime.graph, start, end, "shortest_distance")),
        timed("Dijkstra shortest_time", lambda: shortest_path(runtime.graph, start, end, "shortest_time")),
        timed("A* shortest_time", lambda: shortest_path_astar(runtime.graph, start, end, "shortest_time")),
    ]

    print("| Scenario | Time ms | Distance m | Road count |")
    print("| --- | ---: | ---: | ---: |")
    for label, elapsed_ms, distance, road_count in rows:
        print(f"| {label} | {elapsed_ms:.3f} | {distance:.2f} | {road_count} |")


if __name__ == "__main__":
    main()
