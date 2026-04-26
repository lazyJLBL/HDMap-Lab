from __future__ import annotations

from app.core.geometry import haversine_distance
from app.map_matching.candidate_search import CandidateSearcher, RoadCandidate
from app.map_matching.cost_model import (
    direction_cost,
    emission_log_probability,
    road_class_prior,
    trajectory_heading,
    transition_log_probability,
)
from app.map_matching.nearest_matcher import _dedupe_sequence
from app.models import Trajectory
from app.routing.graph_builder import RoadGraph


def match_hmm(
    trajectory: Trajectory,
    searcher: CandidateSearcher,
    graph: RoadGraph,
    k: int = 5,
    sigma: float = 20.0,
    beta: float = 50.0,
    heading_weight: float = 4.0,
    road_class_weight: float = 0.4,
) -> dict:
    candidate_layers = [
        searcher.nearby_roads(point.coordinate, k) for point in trajectory.points
    ]
    if not candidate_layers or any(not layer for layer in candidate_layers):
        return {
            "trajectory_id": trajectory.id,
            "algorithm": "hmm",
            "matched_road_sequence": [],
            "confidence": 0.0,
            "matches": [],
        }

    dp: list[dict[int, float]] = []
    back: list[dict[int, int]] = []
    first_heading = trajectory_heading(trajectory, 0)
    first_scores = {
        idx: emission_log_probability(candidate, sigma)
        - heading_weight * direction_cost(candidate, first_heading)
        - road_class_weight * road_class_prior(candidate)
        for idx, candidate in enumerate(candidate_layers[0])
    }
    dp.append(first_scores)
    back.append({})

    for layer_index in range(1, len(candidate_layers)):
        prev_layer = candidate_layers[layer_index - 1]
        curr_layer = candidate_layers[layer_index]
        gps_distance = haversine_distance(
            trajectory.coordinates[layer_index - 1],
            trajectory.coordinates[layer_index],
        )
        gps_heading = trajectory_heading(trajectory, layer_index)
        scores: dict[int, float] = {}
        parents: dict[int, int] = {}
        for curr_idx, current in enumerate(curr_layer):
            emission = (
                emission_log_probability(current, sigma)
                - heading_weight * direction_cost(current, gps_heading)
                - road_class_weight * road_class_prior(current)
            )
            best_score = -1_000_000_000.0
            best_parent = 0
            for prev_idx, previous in enumerate(prev_layer):
                score = (
                    dp[layer_index - 1][prev_idx]
                    + transition_log_probability(graph, previous, current, gps_distance, beta)
                    + emission
                )
                if score > best_score:
                    best_score = score
                    best_parent = prev_idx
            scores[curr_idx] = best_score
            parents[curr_idx] = best_parent
        dp.append(scores)
        back.append(parents)

    last_idx = max(dp[-1], key=lambda idx: dp[-1][idx])
    chosen_indices = [last_idx]
    for layer_index in range(len(candidate_layers) - 1, 0, -1):
        last_idx = back[layer_index][last_idx]
        chosen_indices.append(last_idx)
    chosen_indices.reverse()

    chosen: list[RoadCandidate] = [
        candidate_layers[layer][candidate_idx]
        for layer, candidate_idx in enumerate(chosen_indices)
    ]
    matches = [
        {
            "point_index": index,
            "candidate_count": len(candidate_layers[index]),
            "matched_road_id": candidate.road.id,
            "distance": candidate.distance,
            "projection_point": [candidate.projection_point[0], candidate.projection_point[1]],
            "emission_prob": round(_emission_score(candidate.distance, sigma), 4),
            "heading_cost": round(direction_cost(candidate, trajectory_heading(trajectory, index)), 4),
            "road_class_prior": round(road_class_prior(candidate), 4),
            "travel_direction": candidate.travel_direction,
        }
        for index, candidate in enumerate(chosen)
    ]
    avg_distance = sum(candidate.distance for candidate in chosen) / len(chosen)
    return {
        "trajectory_id": trajectory.id,
        "algorithm": "hmm",
        "matched_road_sequence": _dedupe_sequence([candidate.road.id for candidate in chosen]),
        "confidence": round(1.0 / (1.0 + avg_distance / max(sigma, 1.0)), 3),
        "matches": matches,
    }


def _emission_score(distance: float, sigma: float) -> float:
    return 1.0 / (1.0 + distance / max(sigma, 1.0))
