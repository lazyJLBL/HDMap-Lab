from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable

from app.core.geojson import normalize_polygon
from app.routing.advanced import ExplainedPathResult, shortest_path_explained
from app.routing.constraints import edges_intersecting_polygons
from app.storage.runtime import RuntimeState


def run_routing_benchmark(
    output: str | Path | None = None,
    iterations: int = 30,
    db_path: str | Path = "data/routing_benchmark.sqlite",
) -> dict[str, Any]:
    runtime = RuntimeState(db_path)
    runtime.load_sample()
    start = runtime.graph.nearest_node_id((116.390, 39.900))
    end = runtime.graph.nearest_node_id((116.410, 39.920))
    if start is None or end is None:
        raise RuntimeError("sample graph is missing")

    avoid_polygon = normalize_polygon(
        [
            [
                [116.398, 39.908],
                [116.406, 39.908],
                [116.406, 39.916],
                [116.398, 39.916],
                [116.398, 39.908],
            ]
        ]
    )
    avoided_edges = edges_intersecting_polygons(runtime.roads, [avoid_polygon])
    scenarios: list[tuple[str, Callable[[], ExplainedPathResult]]] = [
        (
            "dijkstra_distance",
            lambda: shortest_path_explained(runtime.graph, start, end, algorithm="dijkstra", cost_mode="distance", turn_cost_enabled=False),
        ),
        (
            "astar_distance",
            lambda: shortest_path_explained(runtime.graph, start, end, algorithm="astar", cost_mode="distance", turn_cost_enabled=False),
        ),
        (
            "dijkstra_time",
            lambda: shortest_path_explained(runtime.graph, start, end, algorithm="dijkstra", cost_mode="time", turn_cost_enabled=False),
        ),
        (
            "astar_time",
            lambda: shortest_path_explained(runtime.graph, start, end, algorithm="astar", cost_mode="time", turn_cost_enabled=False),
        ),
        (
            "astar_with_turn_cost",
            lambda: shortest_path_explained(runtime.graph, start, end, algorithm="astar", cost_mode="distance", turn_cost_enabled=True),
        ),
        (
            "astar_with_avoid_polygon",
            lambda: shortest_path_explained(
                runtime.graph,
                start,
                end,
                algorithm="astar",
                cost_mode="distance",
                turn_cost_enabled=True,
                excluded_edges=avoided_edges,
            ),
        ),
    ]

    rows = [_measure(label, factory, iterations) for label, factory in scenarios]
    payload = {
        "start_node": start,
        "end_node": end,
        "iterations": iterations,
        "results": rows,
        "debug_layers": {"avoid_polygon_edges": sorted(avoided_edges)},
    }
    if output is not None:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _measure(label: str, factory: Callable[[], ExplainedPathResult], iterations: int) -> dict[str, Any]:
    latencies: list[float] = []
    result = factory()
    for _ in range(iterations):
        started = time.perf_counter()
        result = factory()
        latencies.append((time.perf_counter() - started) * 1000.0)
    return {
        "scenario": label,
        "latency_ms": statistics.mean(latencies) if latencies else 0.0,
        "p50_ms": _percentile(latencies, 0.50),
        "p95_ms": _percentile(latencies, 0.95),
        "visited_nodes": result.visited_nodes,
        "path_length_m": result.distance,
        "path_time_s": result.estimated_time,
        "turn_count": result.turn_count,
        "edge_count": len(result.road_sequence),
        "found": result.found,
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    index = min(len(values) - 1, max(0, round((len(values) - 1) * percentile)))
    return values[index]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run HDMap-Lab routing benchmark v2.")
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--output", default="docs/assets/routing_benchmark.json")
    args = parser.parse_args()

    payload = run_routing_benchmark(output=args.output, iterations=args.iterations)
    for row in payload["results"]:
        print(
            f"{row['scenario']}: p95={row['p95_ms']:.4f}ms "
            f"length={row['path_length_m']:.2f}m turns={row['turn_count']}"
        )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
