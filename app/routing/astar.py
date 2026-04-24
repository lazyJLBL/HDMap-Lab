from __future__ import annotations

import heapq
from math import inf

from app.core.geometry import haversine_distance
from app.routing.dijkstra import PathResult, _reconstruct
from app.routing.graph_builder import GraphArc, RoadGraph


def shortest_path_astar(
    graph: RoadGraph,
    start_node: str,
    end_node: str,
    mode: str = "shortest_distance",
    excluded_edges: set[str] | None = None,
) -> PathResult:
    excluded_edges = excluded_edges or set()
    queue: list[tuple[float, float, str]] = [(0.0, 0.0, start_node)]
    best: dict[str, float] = {start_node: 0.0}
    previous: dict[str, tuple[str, GraphArc]] = {}

    while queue:
        _, cost, node = heapq.heappop(queue)
        if node == end_node:
            break
        if cost > best.get(node, inf):
            continue
        for arc in graph.adjacency.get(node, []):
            if arc.edge_id in excluded_edges:
                continue
            next_cost = cost + graph.arc_weight(arc, mode)
            if next_cost < best.get(arc.to_node, inf):
                best[arc.to_node] = next_cost
                previous[arc.to_node] = (node, arc)
                priority = next_cost + _heuristic(graph, arc.to_node, end_node, mode)
                heapq.heappush(queue, (priority, next_cost, arc.to_node))

    if end_node not in best:
        return PathResult(False, 0.0, 0.0, [], [], [])
    return _reconstruct(start_node, end_node, previous)


def _heuristic(graph: RoadGraph, node_id: str, end_node_id: str, mode: str) -> float:
    node = graph.nodes[node_id]
    end = graph.nodes[end_node_id]
    distance = haversine_distance(node.coordinate, end.coordinate)
    if mode == "shortest_time":
        return distance / 33.33
    return distance

