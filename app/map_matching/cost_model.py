from __future__ import annotations

from math import inf

from app.core.geometry import angle_difference, bearing, haversine_distance
from app.map_matching.candidate_search import RoadCandidate
from app.models import Trajectory
from app.routing.dijkstra import shortest_path
from app.routing.graph_builder import RoadGraph


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
        "primary": 0.08,
        "secondary": 0.12,
        "tertiary": 0.16,
        "residential": 0.22,
        "service": 0.32,
        "local": 0.22,
    }
    return priors.get(candidate.road.road_class, priors.get(candidate.road.road_type, 0.25))


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
    return min(1.0, (observed_speed_kph - allowed) / max(allowed, 1.0))


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
    return -0.5 * (candidate.distance / max(sigma, 1.0)) ** 2


def candidate_total_cost(
    graph: RoadGraph,
    candidate: RoadCandidate,
    gps_heading: float | None,
    previous: RoadCandidate | None,
    weights: tuple[float, float, float, float, float] = (1.0, 30.0, 0.02, 25.0, 12.0),
) -> dict[str, float]:
    distance = candidate.distance
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
