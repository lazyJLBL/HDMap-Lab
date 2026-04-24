from __future__ import annotations

import heapq
from dataclasses import dataclass
from math import inf

from app.routing.graph_builder import GraphArc, RoadGraph


@dataclass(slots=True)
class PathResult:
    found: bool
    distance: float
    estimated_time: float
    road_sequence: list[str]
    geometry: list[tuple[float, float]]
    node_sequence: list[str]


def shortest_path(
    graph: RoadGraph,
    start_node: str,
    end_node: str,
    mode: str = "shortest_distance",
    excluded_edges: set[str] | None = None,
) -> PathResult:
    excluded_edges = excluded_edges or set()
    queue: list[tuple[float, str]] = [(0.0, start_node)]
    best: dict[str, float] = {start_node: 0.0}
    previous: dict[str, tuple[str, GraphArc]] = {}

    while queue:
        cost, node = heapq.heappop(queue)
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
                heapq.heappush(queue, (next_cost, arc.to_node))

    if end_node not in best:
        return PathResult(False, 0.0, 0.0, [], [], [])
    return _reconstruct(start_node, end_node, previous)


def _reconstruct(
    start_node: str,
    end_node: str,
    previous: dict[str, tuple[str, GraphArc]],
) -> PathResult:
    arcs: list[GraphArc] = []
    node = end_node
    nodes = [end_node]
    while node != start_node:
        prev_node, arc = previous[node]
        arcs.append(arc)
        node = prev_node
        nodes.append(node)
    arcs.reverse()
    nodes.reverse()

    geometry: list[tuple[float, float]] = []
    distance = 0.0
    estimated_time = 0.0
    roads: list[str] = []
    for arc in arcs:
        distance += arc.length
        estimated_time += arc.travel_time
        roads.append(arc.edge_id)
        if not geometry:
            geometry.extend(arc.geometry)
        else:
            geometry.extend(arc.geometry[1:])
    return PathResult(True, distance, estimated_time, roads, geometry, nodes)

