from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from math import inf

from app.routing.dijkstra import PathResult
from app.routing.graph_builder import GraphArc, RoadGraph
from app.routing.turn_cost import road_class_preference_cost, turn_cost_seconds


@dataclass(slots=True)
class RouteStep:
    edge_id: str
    from_node: str
    to_node: str
    length: float
    travel_time: float
    turn_cost: float
    road_class_cost: float

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "length": self.length,
            "travel_time": self.travel_time,
            "turn_cost": self.turn_cost,
            "road_class_cost": self.road_class_cost,
        }


@dataclass(slots=True)
class ExplainedPathResult(PathResult):
    steps: list[RouteStep] = field(default_factory=list)
    cost_breakdown: dict[str, float] = field(default_factory=dict)


def shortest_path_explained(
    graph: RoadGraph,
    start_node: str,
    end_node: str,
    mode: str = "shortest_distance",
    excluded_edges: set[str] | None = None,
    preferred_road_classes: list[str] | None = None,
    turn_penalty_seconds: float = 8.0,
) -> ExplainedPathResult:
    excluded_edges = excluded_edges or set()
    start_state = (start_node, "")
    counter = itertools.count()
    queue: list[tuple[float, int, tuple[str, str], GraphArc | None]] = [(0.0, next(counter), start_state, None)]
    best: dict[tuple[str, str], float] = {start_state: 0.0}
    previous: dict[tuple[str, str], tuple[tuple[str, str], GraphArc, float, float]] = {}

    best_end: tuple[str, str] | None = None
    while queue:
        cost, _, state, prev_arc = heapq.heappop(queue)
        node, _ = state
        if node == end_node:
            best_end = state
            break
        if cost > best.get(state, inf):
            continue
        for arc in graph.adjacency.get(node, []):
            if arc.edge_id in excluded_edges:
                continue
            turn = turn_cost_seconds(prev_arc, arc, turn_penalty_seconds)
            class_cost = road_class_preference_cost(arc, preferred_road_classes)
            base_cost = graph.arc_weight(arc, mode)
            next_cost = cost + base_cost + turn + class_cost
            next_state = (arc.to_node, arc.edge_id)
            if next_cost < best.get(next_state, inf):
                best[next_state] = next_cost
                previous[next_state] = (state, arc, turn, class_cost)
                heapq.heappush(queue, (next_cost, next(counter), next_state, arc))

    if best_end is None:
        return ExplainedPathResult(False, 0.0, 0.0, [], [], [], [], {})
    return _reconstruct_explained(start_state, best_end, previous)


def _reconstruct_explained(
    start_state: tuple[str, str],
    end_state: tuple[str, str],
    previous: dict[tuple[str, str], tuple[tuple[str, str], GraphArc, float, float]],
) -> ExplainedPathResult:
    records: list[tuple[GraphArc, float, float]] = []
    nodes = [end_state[0]]
    state = end_state
    while state != start_state:
        prev_state, arc, turn, class_cost = previous[state]
        records.append((arc, turn, class_cost))
        state = prev_state
        nodes.append(state[0])
    records.reverse()
    nodes.reverse()

    geometry: list[tuple[float, float]] = []
    roads: list[str] = []
    steps: list[RouteStep] = []
    distance = 0.0
    travel_time = 0.0
    turn_cost_total = 0.0
    road_class_cost_total = 0.0
    for arc, turn, class_cost in records:
        distance += arc.length
        travel_time += arc.travel_time
        turn_cost_total += turn
        road_class_cost_total += class_cost
        roads.append(arc.edge_id)
        steps.append(RouteStep(arc.edge_id, arc.from_node, arc.to_node, arc.length, arc.travel_time, turn, class_cost))
        if not geometry:
            geometry.extend(arc.geometry)
        else:
            geometry.extend(arc.geometry[1:])
    return ExplainedPathResult(
        True,
        distance,
        travel_time,
        roads,
        geometry,
        nodes,
        steps,
        {
            "distance_m": distance,
            "travel_time_s": travel_time,
            "turn_cost_s": turn_cost_total,
            "road_class_cost": road_class_cost_total,
        },
    )
