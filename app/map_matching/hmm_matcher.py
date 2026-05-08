from __future__ import annotations

from app.core.geometry import haversine_distance
from app.map_matching.candidate_search import CandidateSearcher, RoadCandidate
from app.map_matching.cost_model import HMMCostWeights, breakdown_with_total, cost_breakdown, trajectory_heading
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
    cost_weights: HMMCostWeights | None = None,
    emission_weight: float | None = None,
    transition_weight: float | None = None,
    heading_weight: float | None = None,
    turn_weight: float | None = None,
    road_class_weight: float | None = None,
    oneway_weight: float | None = None,
    layer_weight: float | None = None,
    speed_weight: float | None = None,
    beam_width: int | None = None,
    radius_m: float = 150.0,
    step_seconds: float | None = None,
) -> dict:
    weights = (cost_weights or HMMCostWeights()).with_overrides(
        emission_weight=emission_weight,
        transition_weight=transition_weight,
        heading_weight=heading_weight,
        turn_weight=turn_weight,
        road_class_weight=road_class_weight,
        oneway_weight=oneway_weight,
        layer_weight=layer_weight,
        speed_weight=speed_weight,
    )
    candidate_layers = [
        searcher.search(point.coordinate, radius_m=radius_m, k=k, heading=trajectory_heading(trajectory, index))
        for index, point in enumerate(trajectory.points)
    ]
    if not candidate_layers:
        return _empty_result(trajectory.id)
    if any(not layer for layer in candidate_layers):
        return _fallback_empty_candidate_result(trajectory, searcher, k, radius_m)

    dp: list[dict[int, float]] = []
    back: list[dict[int, int]] = []
    breakdown_layers: list[dict[int, dict[str, float]]] = []
    first_heading = trajectory_heading(trajectory, 0)
    first_scores: dict[int, float] = {}
    first_breakdowns: dict[int, dict[str, float]] = {}
    for idx, candidate in enumerate(candidate_layers[0]):
        breakdown = cost_breakdown(graph, candidate, first_heading, sigma=sigma, beta=beta, weights=weights)
        first_breakdowns[idx] = breakdown
        first_scores[idx] = breakdown_with_total(breakdown)["total"]
    dp.append(_prune(first_scores, beam_width))
    back.append({})
    breakdown_layers.append(first_breakdowns)

    for layer_index in range(1, len(candidate_layers)):
        prev_layer = candidate_layers[layer_index - 1]
        curr_layer = candidate_layers[layer_index]
        gps_distance = haversine_distance(trajectory.coordinates[layer_index - 1], trajectory.coordinates[layer_index])
        gps_heading = trajectory_heading(trajectory, layer_index)
        scores: dict[int, float] = {}
        parents: dict[int, int] = {}
        layer_breakdowns: dict[int, dict[str, float]] = {}
        for curr_idx, current in enumerate(curr_layer):
            best_score = 1_000_000_000.0
            best_parent = next(iter(dp[layer_index - 1]))
            best_breakdown: dict[str, float] = {}
            for prev_idx in dp[layer_index - 1]:
                previous = prev_layer[prev_idx]
                breakdown = cost_breakdown(
                    graph,
                    current,
                    gps_heading,
                    previous=previous,
                    gps_distance=gps_distance,
                    step_seconds=step_seconds,
                    sigma=sigma,
                    beta=beta,
                    weights=weights,
                )
                score = dp[layer_index - 1][prev_idx] + breakdown_with_total(breakdown)["total"]
                if score < best_score:
                    best_score = score
                    best_parent = prev_idx
                    best_breakdown = breakdown
            scores[curr_idx] = best_score
            parents[curr_idx] = best_parent
            layer_breakdowns[curr_idx] = best_breakdown
        scores = _prune(scores, beam_width)
        parents = {idx: parent for idx, parent in parents.items() if idx in scores}
        dp.append(scores)
        back.append(parents)
        breakdown_layers.append(layer_breakdowns)

    last_idx = min(dp[-1], key=lambda idx: dp[-1][idx])
    chosen_indices = [last_idx]
    for layer_index in range(len(candidate_layers) - 1, 0, -1):
        last_idx = back[layer_index][last_idx]
        chosen_indices.append(last_idx)
    chosen_indices.reverse()

    chosen = [candidate_layers[layer][candidate_idx] for layer, candidate_idx in enumerate(chosen_indices)]
    matches = [
        {
            "point_index": index,
            "candidate_count": len(candidate_layers[index]),
            "matched_road_id": candidate.road.id,
            "distance": candidate.distance_m,
            "distance_m": candidate.distance_m,
            "projection_point": [candidate.projected_point[0], candidate.projected_point[1]],
            "projected_point": [candidate.projected_point[0], candidate.projected_point[1]],
            "travel_direction": candidate.travel_direction,
            "cost_breakdown": breakdown_with_total(breakdown_layers[index][chosen_indices[index]]),
            "candidates": [item.to_dict() for item in candidate_layers[index]],
        }
        for index, candidate in enumerate(chosen)
    ]
    avg_distance = sum(candidate.distance_m for candidate in chosen) / len(chosen)
    confidence = _confidence(dp[-1], avg_distance, sigma)
    return {
        "trajectory_id": trajectory.id,
        "algorithm": "hmm",
        "matched_road_sequence": _dedupe_sequence([candidate.road.id for candidate in chosen]),
        "confidence": confidence,
        "matches": matches,
        "candidates": [[candidate.to_dict() for candidate in layer] for layer in candidate_layers],
        "chosen_path": [candidate.road.id for candidate in chosen],
        "metrics": {
            "candidate_count_avg": sum(len(layer) for layer in candidate_layers) / len(candidate_layers),
            "avg_distance_m": avg_distance,
            "dp_final_cost": min(dp[-1].values()),
        },
        "debug_layers": _debug_layers(trajectory, chosen, candidate_layers),
    }


def _prune(scores: dict[int, float], beam_width: int | None) -> dict[int, float]:
    if beam_width is None or beam_width <= 0 or len(scores) <= beam_width:
        return scores
    keep = {idx for idx, _score in sorted(scores.items(), key=lambda item: item[1])[:beam_width]}
    return {idx: score for idx, score in scores.items() if idx in keep}


def _confidence(final_scores: dict[int, float], avg_distance: float, sigma: float) -> float:
    if not final_scores:
        return 0.0
    ordered = sorted(final_scores.values())
    margin = (ordered[1] - ordered[0]) if len(ordered) > 1 else 1.0
    distance_term = 1.0 / (1.0 + avg_distance / max(sigma, 1.0))
    margin_term = min(1.0, max(0.0, margin / 5.0))
    return round(0.75 * distance_term + 0.25 * margin_term, 3)


def _fallback_empty_candidate_result(
    trajectory: Trajectory,
    searcher: CandidateSearcher,
    k: int,
    radius_m: float,
) -> dict:
    matches = []
    for index, point in enumerate(trajectory.points):
        candidates = searcher.search(point.coordinate, radius_m=radius_m * 10, k=k, allow_fallback=True)
        if not candidates:
            continue
        candidate = candidates[0]
        matches.append(
            {
                "point_index": index,
                "candidate_count": len(candidates),
                "matched_road_id": candidate.road.id,
                "distance": candidate.distance_m,
                "projection_point": [candidate.projected_point[0], candidate.projected_point[1]],
                "cost_breakdown": {},
                "candidates": [item.to_dict() for item in candidates],
            }
        )
    return {
        "trajectory_id": trajectory.id,
        "algorithm": "hmm",
        "matched_road_sequence": _dedupe_sequence([match["matched_road_id"] for match in matches]),
        "confidence": 0.0 if not matches else 0.25,
        "matches": matches,
        "candidates": [match.get("candidates", []) for match in matches],
        "chosen_path": [match["matched_road_id"] for match in matches],
        "metrics": {"candidate_empty_fallback": True},
        "debug_layers": {},
    }


def _empty_result(trajectory_id: str) -> dict:
    return {
        "trajectory_id": trajectory_id,
        "algorithm": "hmm",
        "matched_road_sequence": [],
        "confidence": 0.0,
        "matches": [],
        "candidates": [],
        "chosen_path": [],
        "metrics": {},
        "debug_layers": {},
    }


def _debug_layers(
    trajectory: Trajectory,
    chosen: list[RoadCandidate],
    candidate_layers: list[list[RoadCandidate]],
) -> dict:
    return {
        "gps_points": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"layer": "gps_points", "point_index": index},
                    "geometry": {"type": "Point", "coordinates": [point.lon, point.lat]},
                }
                for index, point in enumerate(trajectory.points)
            ],
        },
        "matched_points": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"layer": "matched_points", "point_index": index, "road_id": candidate.road.id},
                    "geometry": {"type": "Point", "coordinates": [candidate.projected_point[0], candidate.projected_point[1]]},
                }
                for index, candidate in enumerate(chosen)
            ],
        },
        "candidate_roads": {
            "type": "FeatureCollection",
            "features": [candidate.road.to_geojson_feature() for layer in candidate_layers for candidate in layer],
        },
    }
