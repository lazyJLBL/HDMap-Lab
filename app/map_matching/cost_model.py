from __future__ import annotations

from dataclasses import dataclass, replace
from math import inf

from app.core.geometry import angle_difference, bearing, haversine_distance
from app.map_matching.candidate_search import RoadCandidate
from app.models import Trajectory
from app.routing.dijkstra import shortest_path
from app.routing.graph_builder import RoadGraph


@dataclass(frozen=True, slots=True)
class HMMCostWeights:
    emission_weight: float = 1.0
    transition_weight: float = 1.0
    heading_weight: float = 4.0
    turn_weight: float = 2.0
    road_class_weight: float = 5.0
    oneway_weight: float = 25.0
    layer_weight: float = 6.0
    speed_weight: float = 1.0

    def with_overrides(self, **overrides: float | None) -> "HMMCostWeights":
        active = {key: value for key, value in overrides.items() if value is not None}
        if not active:
            return self
        return replace(self, **active)


def trajectory_heading(trajectory: Trajectory, index: int) -> float | None:
    points = trajectory.coordinates
    if len(points) < 2:
        return None
    if index < len(points) - 1:
        return bearing(points[index], points[index + 1])
    return bearing(points[index - 1], points[index])


def direction_cost(candidate: RoadCandidate, gps_heading: float | None) -> float:
    if gps_heading is None:
        return 0.0
    if candidate.road.oneway:
        diff = angle_difference(gps_heading, candidate.road_heading)
    else:
        diff = min(
            angle_difference(gps_heading, candidate.road_heading),
            angle_difference(gps_heading, (candidate.road_heading + 180.0) % 360.0),
        )
    return diff / 180.0


def turn_penalty(previous: RoadCandidate | None, current: RoadCandidate) -> float:
    if previous is None or previous.road.id == current.road.id:
        return 0.0
    return angle_difference(previous.road_heading, current.road_heading) / 180.0


def road_class_prior(candidate: RoadCandidate) -> float:
    priors = {
        "motorway": 0.0,
        "trunk": 0.05,
        "primary": 0.02,
        "secondary": 0.08,
        "tertiary": 0.14,
        "residential": 0.24,
        "local": 0.24,
        "service": 0.55,
    }
    return priors.get(candidate.road.road_class, priors.get(candidate.road.road_type, 0.3))


def speed_feasibility_penalty(
    previous: RoadCandidate | None,
    current: RoadCandidate,
    gps_distance: float | None = None,
    step_seconds: float | None = None,
) -> float:
    if previous is None or gps_distance is None or step_seconds is None or step_seconds <= 0:
        return 0.0
    observed_speed_kph = gps_distance / step_seconds * 3.6
    allowed = max(previous.road.speed_limit, current.road.speed_limit) * 1.35 + 10.0
    if observed_speed_kph <= allowed:
        return 0.0
    return min(10.0, (observed_speed_kph - allowed) / max(allowed, 1.0))


def edge_connectivity_distance(
    graph: RoadGraph,
    previous: RoadCandidate,
    current: RoadCandidate,
    mode: str = "shortest_distance",
) -> float:
    if previous.road.id == current.road.id:
        return 0.0
    starts = [previous.road.from_node, previous.road.to_node]
    ends = [current.road.from_node, current.road.to_node]
    best = inf
    for start in starts:
        for end in ends:
            result = shortest_path(graph, start, end, mode=mode)
            if result.found:
                best = min(best, result.distance)
    return best


def emission_probability(candidate: RoadCandidate, sigma: float = 20.0) -> float:
    return max(0.0, min(1.0, _exp_like(-0.5 * (candidate.distance_m / max(sigma, 1.0)) ** 2)))


def transition_probability(
    graph: RoadGraph,
    previous: RoadCandidate,
    current: RoadCandidate,
    gps_distance: float,
    beta: float = 50.0,
) -> float:
    network_distance = edge_connectivity_distance(graph, previous, current)
    if network_distance == inf:
        return 0.0
    return max(0.0, min(1.0, _exp_like(-abs(network_distance - gps_distance) / max(beta, 1.0))))


def cost_breakdown(
    graph: RoadGraph,
    candidate: RoadCandidate,
    gps_heading: float | None,
    previous: RoadCandidate | None = None,
    gps_distance: float | None = None,
    step_seconds: float | None = None,
    sigma: float = 20.0,
    beta: float = 50.0,
    weights: HMMCostWeights | None = None,
) -> dict[str, float]:
    weights = weights or HMMCostWeights()
    emission = 0.5 * (candidate.distance_m / max(sigma, 1.0)) ** 2 * weights.emission_weight
    heading = direction_cost(candidate, gps_heading) * weights.heading_weight
    speed = speed_feasibility_penalty(previous, candidate, gps_distance, step_seconds) * weights.speed_weight
    turn = turn_penalty(previous, candidate) * weights.turn_weight
    road_class = road_class_prior(candidate) * weights.road_class_weight
    oneway = 0.0 if candidate.is_oneway_compatible else weights.oneway_weight
    layer = 0.0
    transition = 0.0
    if previous is not None and gps_distance is not None:
        if previous.layer != candidate.layer:
            layer = weights.layer_weight
        network_distance = edge_connectivity_distance(graph, previous, candidate)
        if network_distance == inf:
            transition = 1_000_000.0 * weights.transition_weight
        else:
            transition = abs(network_distance - gps_distance) / max(beta, 1.0) * weights.transition_weight
    return {
        "emission": emission,
        "transition": transition,
        "heading": heading,
        "speed": speed,
        "turn": turn,
        "road_class": road_class,
        "oneway": oneway,
        "layer": layer,
    }


def total_cost(breakdown: dict[str, float]) -> float:
    return sum(breakdown.values())


def transition_log_probability(
    graph: RoadGraph,
    previous: RoadCandidate,
    current: RoadCandidate,
    gps_distance: float,
    beta: float,
    turn_weight: float = 1.5,
    class_weight: float = 0.5,
) -> float:
    network_distance = edge_connectivity_distance(graph, previous, current)
    if network_distance == inf:
        return -1_000_000.0
    transition = -abs(network_distance - gps_distance) / max(beta, 1.0)
    return transition - turn_weight * turn_penalty(previous, current) - class_weight * road_class_prior(current)


def emission_log_probability(candidate: RoadCandidate, sigma: float) -> float:
    return -0.5 * (candidate.distance_m / max(sigma, 1.0)) ** 2


def candidate_total_cost(
    graph: RoadGraph,
    candidate: RoadCandidate,
    gps_heading: float | None,
    previous: RoadCandidate | None,
    weights: tuple[float, float, float, float, float] = (1.0, 30.0, 0.02, 25.0, 12.0),
) -> dict[str, float]:
    distance = candidate.distance_m
    direction = direction_cost(candidate, gps_heading)
    connectivity = 0.0
    if previous is not None:
        conn = edge_connectivity_distance(graph, previous, candidate)
        connectivity = conn if conn != inf else 1_000_000.0
    turn = turn_penalty(previous, candidate)
    road_class = road_class_prior(candidate)
    total = (
        weights[0] * distance
        + weights[1] * direction
        + weights[2] * connectivity
        + weights[3] * turn
        + weights[4] * road_class
    )
    return {
        "distance_cost": distance,
        "direction_cost": direction,
        "connectivity_cost": connectivity,
        "turn_cost": turn,
        "road_class_cost": road_class,
        "total_cost": total,
    }


def gps_step_distance(trajectory: Trajectory, index: int) -> float:
    if index <= 0:
        return 0.0
    return haversine_distance(trajectory.coordinates[index - 1], trajectory.coordinates[index])


def breakdown_with_total(breakdown: dict[str, float]) -> dict[str, float]:
    return breakdown | {"total": total_cost(breakdown)}


def _exp_like(value: float) -> float:
    if value < -50:
        return 0.0
    return 2.718281828459045**value
