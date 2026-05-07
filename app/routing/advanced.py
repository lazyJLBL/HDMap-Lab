from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from math import inf
from typing import Any

from app.core.geojson import feature_collection
from app.core.geometry import haversine_distance
from app.routing.dijkstra import PathResult
from app.routing.graph_builder import GraphArc, RoadGraph
from app.routing.turn_cost import (
    classify_turn,
    compute_turn_angle,
    restricted_turn,
    road_class_preference_cost,
    turn_penalty_seconds,
)

TURN_SECOND_TO_METER = 8.33


@dataclass(slots=True)
class RouteStep:
    road_id: str
    from_node: str
    to_node: str
    instruction: str
    distance_m: float
    travel_time_s: float
    road_class: str
    turn_type: str
    turn_angle_degrees: float
    cost: float
    cost_breakdown: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "road_id": self.road_id,
            "edge_id": self.road_id,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "instruction": self.instruction,
            "distance_m": self.distance_m,
            "length": self.distance_m,
            "travel_time_s": self.travel_time_s,
            "travel_time": self.travel_time_s,
            "road_class": self.road_class,
            "turn_type": self.turn_type,
            "turn_angle_degrees": self.turn_angle_degrees,
            "turn_cost": self.cost_breakdown.get("turn_penalty", 0.0),
            "road_class_cost": self.cost_breakdown.get("road_class_preference", 0.0),
            "cost": self.cost,
            "cost_breakdown": self.cost_breakdown,
        }


@dataclass(slots=True)
class RoutingOptions:
    cost_mode: str = "distance"
    algorithm: str = "astar"
    turn_cost_enabled: bool = True
    turn_penalty_seconds: float = 8.0
    prefer_road_classes: list[str] = field(default_factory=list)
    avoid_road_classes: list[str] = field(default_factory=list)
    soft_avoid_edges: set[str] = field(default_factory=set)
    soft_avoid_penalty: float = 10_000.0
    custom_weights: dict[str, float] = field(default_factory=dict)
    speed_profile: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class ExplainedPathResult(PathResult):
    steps: list[RouteStep] = field(default_factory=list)
    cost_breakdown: dict[str, float] = field(default_factory=dict)
    total_cost: float = 0.0
    visited_nodes: int = 0
    turn_count: int = 0
    debug_layers: dict[str, Any] = field(default_factory=dict)


def shortest_path_explained(
    graph: RoadGraph,
    start_node: str,
    end_node: str,
    mode: str = "shortest_distance",
    excluded_edges: set[str] | None = None,
    preferred_road_classes: list[str] | None = None,
    turn_penalty_seconds: float = 8.0,
    algorithm: str = "astar",
    cost_mode: str | None = None,
    turn_cost_enabled: bool = True,
    prefer_road_classes: list[str] | None = None,
    avoid_road_classes: list[str] | None = None,
    soft_avoid_edges: set[str] | None = None,
    custom_weights: dict[str, float] | None = None,
    speed_profile: dict[str, float] | None = None,
) -> ExplainedPathResult:
    excluded_edges = excluded_edges or set()
    options = RoutingOptions(
        cost_mode=_normalize_cost_mode(cost_mode or mode),
        algorithm=algorithm,
        turn_cost_enabled=turn_cost_enabled,
        turn_penalty_seconds=turn_penalty_seconds,
        prefer_road_classes=prefer_road_classes or preferred_road_classes or [],
        avoid_road_classes=avoid_road_classes or [],
        soft_avoid_edges=soft_avoid_edges or set(),
        custom_weights=custom_weights or {},
        speed_profile=speed_profile or {},
    )

    start_state = (start_node, "")
    counter = itertools.count()
    queue: list[tuple[float, float, int, tuple[str, str]]] = [(0.0, 0.0, next(counter), start_state)]
    best: dict[tuple[str, str], float] = {start_state: 0.0}
    previous: dict[tuple[str, str], tuple[tuple[str, str], GraphArc, dict[str, float], float]] = {}
    visited_nodes: set[str] = set()
    best_end: tuple[str, str] | None = None

    while queue:
        _priority, cost, _, state = heapq.heappop(queue)
        node, _edge_id = state
        if cost > best.get(state, inf):
            continue
        visited_nodes.add(node)
        if node == end_node:
            best_end = state
            break
        previous_arc = previous[state][1] if state in previous else None
        for arc in graph.adjacency.get(node, []):
            if arc.edge_id in excluded_edges or restricted_turn(previous_arc, arc):
                continue
            arc_cost, components = _arc_cost(previous_arc, arc, options)
            next_cost = cost + arc_cost
            next_state = (arc.to_node, arc.edge_id)
            if next_cost < best.get(next_state, inf):
                best[next_state] = next_cost
                previous[next_state] = (state, arc, components, arc_cost)
                heuristic = _heuristic(graph, arc.to_node, end_node, options) if algorithm == "astar" else 0.0
                heapq.heappush(queue, (next_cost + heuristic, next_cost, next(counter), next_state))

    if best_end is None:
        return ExplainedPathResult(False, 0.0, 0.0, [], [], [], [], {}, 0.0, len(visited_nodes), 0, {})
    return _reconstruct_explained(start_state, best_end, previous, graph, excluded_edges, len(visited_nodes))


def _arc_cost(previous: GraphArc | None, arc: GraphArc, options: RoutingOptions) -> tuple[float, dict[str, float]]:
    travel_time = _travel_time_with_profile(arc, options.speed_profile)
    turn_seconds = turn_penalty_seconds(previous, arc, options.turn_penalty_seconds) if options.turn_cost_enabled else 0.0
    class_penalty = road_class_preference_cost(arc, options.prefer_road_classes, options.avoid_road_classes)
    avoid_penalty = options.soft_avoid_penalty if arc.edge_id in options.soft_avoid_edges else 0.0
    components = {
        "distance": arc.length,
        "travel_time": travel_time,
        "turn_penalty": turn_seconds,
        "avoid_penalty": avoid_penalty,
        "road_class_preference": class_penalty,
    }
    if options.cost_mode == "time":
        return travel_time + turn_seconds + class_penalty / max(1.0, arc.speed_limit), components
    if options.cost_mode == "custom":
        weights = {
            "distance": options.custom_weights.get("distance", 1.0),
            "travel_time": options.custom_weights.get("travel_time", 0.0),
            "turn_penalty": options.custom_weights.get("turn_penalty", TURN_SECOND_TO_METER),
            "avoid_penalty": options.custom_weights.get("avoid_penalty", 1.0),
            "road_class_preference": options.custom_weights.get("road_class_preference", 1.0),
        }
        return sum(components[key] * weights[key] for key in weights), components
    return arc.length + turn_seconds * TURN_SECOND_TO_METER + class_penalty + avoid_penalty, components


def _travel_time_with_profile(arc: GraphArc, speed_profile: dict[str, float]) -> float:
    speed = speed_profile.get(arc.road_class, arc.speed_limit)
    speed_mps = max(1.0, speed) * 1000.0 / 3600.0
    return arc.length / speed_mps


def _heuristic(graph: RoadGraph, node_id: str, end_node_id: str, options: RoutingOptions) -> float:
    if options.cost_mode == "custom":
        return 0.0
    node = graph.nodes[node_id]
    end = graph.nodes[end_node_id]
    distance = haversine_distance(node.coordinate, end.coordinate)
    if options.cost_mode == "time":
        return distance / graph.max_speed_mps()
    return distance


def _reconstruct_explained(
    start_state: tuple[str, str],
    end_state: tuple[str, str],
    previous: dict[tuple[str, str], tuple[tuple[str, str], GraphArc, dict[str, float], float]],
    graph: RoadGraph,
    excluded_edges: set[str],
    visited_count: int,
) -> ExplainedPathResult:
    records: list[tuple[GraphArc, dict[str, float], float]] = []
    nodes = [end_state[0]]
    state = end_state
    while state != start_state:
        prev_state, arc, components, arc_cost = previous[state]
        records.append((arc, components, arc_cost))
        state = prev_state
        nodes.append(state[0])
    records.reverse()
    nodes.reverse()

    geometry: list[tuple[float, float]] = []
    roads: list[str] = []
    steps: list[RouteStep] = []
    totals = {"distance": 0.0, "travel_time": 0.0, "turn_penalty": 0.0, "avoid_penalty": 0.0, "road_class_preference": 0.0}
    total_cost = 0.0
    turn_count = 0
    previous_arc: GraphArc | None = None
    for arc, components, arc_cost in records:
        angle = compute_turn_angle(previous_arc, arc)
        turn_type = classify_turn(angle)
        if previous_arc is not None and turn_type != "straight":
            turn_count += 1
        for key, value in components.items():
            totals[key] += value
        total_cost += arc_cost
        roads.append(arc.edge_id)
        steps.append(
            RouteStep(
                road_id=arc.edge_id,
                from_node=arc.from_node,
                to_node=arc.to_node,
                instruction=_instruction(turn_type, previous_arc),
                distance_m=arc.length,
                travel_time_s=arc.travel_time,
                road_class=arc.road_class,
                turn_type=turn_type,
                turn_angle_degrees=angle,
                cost=arc_cost,
                cost_breakdown=components,
            )
        )
        if not geometry:
            geometry.extend(arc.geometry)
        else:
            geometry.extend(arc.geometry[1:])
        previous_arc = arc
    return ExplainedPathResult(
        True,
        totals["distance"],
        totals["travel_time"],
        roads,
        geometry,
        nodes,
        steps,
        totals,
        total_cost,
        visited_count,
        turn_count,
        _debug_layers(graph, geometry, roads, excluded_edges),
    )


def _instruction(turn_type: str, previous_arc: GraphArc | None) -> str:
    if previous_arc is None:
        return "go straight"
    if turn_type == "straight":
        return "go straight"
    if turn_type == "u_turn":
        return "make a u-turn"
    return f"turn {turn_type.replace('_', ' ')}"


def _normalize_cost_mode(mode: str) -> str:
    if mode in {"shortest_time", "time", "fastest_time"}:
        return "time"
    if mode == "custom":
        return "custom"
    return "distance"


def _debug_layers(
    graph: RoadGraph,
    geometry: list[tuple[float, float]],
    road_sequence: list[str],
    excluded_edges: set[str],
) -> dict[str, Any]:
    route_feature = {
        "type": "Feature",
        "properties": {"layer": "route"},
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in geometry]},
    }
    route_roads = [graph.roads[road_id].to_geojson_feature() for road_id in road_sequence if road_id in graph.roads]
    avoided = [graph.roads[road_id].to_geojson_feature() for road_id in excluded_edges if road_id in graph.roads]
    return {
        "route": feature_collection([route_feature]),
        "route_roads": feature_collection(route_roads),
        "avoided_edges": feature_collection(avoided),
    }
