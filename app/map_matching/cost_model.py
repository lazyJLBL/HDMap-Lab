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
    diff = min(
        angle_difference(gps_heading, candidate.road_heading),
        angle_difference(gps_heading, (candidate.road_heading + 180.0) % 360.0),
    )
    return diff / 180.0


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
) -> float:
    network_distance = edge_connectivity_distance(graph, previous, current)
    if network_distance == inf:
        return -1_000_000.0
    return -abs(network_distance - gps_distance) / max(beta, 1.0)


def emission_log_probability(candidate: RoadCandidate, sigma: float) -> float:
    return -0.5 * (candidate.distance / max(sigma, 1.0)) ** 2


def candidate_total_cost(
    graph: RoadGraph,
    candidate: RoadCandidate,
    gps_heading: float | None,
    previous: RoadCandidate | None,
    weights: tuple[float, float, float] = (1.0, 30.0, 0.02),
) -> dict[str, float]:
    distance = candidate.distance
    direction = direction_cost(candidate, gps_heading)
    connectivity = 0.0
    if previous is not None:
        conn = edge_connectivity_distance(graph, previous, candidate)
        connectivity = conn if conn != inf else 1_000_000.0
    total = weights[0] * distance + weights[1] * direction + weights[2] * connectivity
    return {
        "distance_cost": distance,
        "direction_cost": direction,
        "connectivity_cost": connectivity,
        "total_cost": total,
    }


def gps_step_distance(trajectory: Trajectory, index: int) -> float:
    if index <= 0:
        return 0.0
    return haversine_distance(trajectory.coordinates[index - 1], trajectory.coordinates[index])

