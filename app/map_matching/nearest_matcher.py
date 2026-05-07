from __future__ import annotations

from app.map_matching.candidate_search import CandidateSearcher, RoadCandidate
from app.map_matching.cost_model import candidate_total_cost, trajectory_heading
from app.models import Trajectory
from app.routing.graph_builder import RoadGraph


def _match_record(index: int, candidate: RoadCandidate, costs: dict | None = None) -> dict:
    payload = {
        "point_index": index,
        "matched_road_id": candidate.road.id,
        "distance": candidate.distance_m,
        "distance_m": candidate.distance_m,
        "projection_point": [candidate.projected_point[0], candidate.projected_point[1]],
        "projected_point": [candidate.projected_point[0], candidate.projected_point[1]],
        "candidate_count": 1,
    }
    if costs:
        payload.update(costs)
    return payload


def match_nearest(trajectory: Trajectory, searcher: CandidateSearcher, k: int = 5) -> dict:
    matches = []
    candidate_layers = []
    for index, point in enumerate(trajectory.points):
        candidates = searcher.nearby_roads(point.coordinate, k)
        candidate_layers.append(candidates)
        if candidates:
            matches.append(_match_record(index, candidates[0], {"candidate_count": len(candidates), "candidates": [candidate.to_dict() for candidate in candidates]}))
    return {
        "trajectory_id": trajectory.id,
        "algorithm": "nearest",
        "matched_road_sequence": _dedupe_sequence([match["matched_road_id"] for match in matches]),
        "confidence": _distance_confidence(matches),
        "matches": matches,
        "metrics": {"candidate_count_avg": sum(len(layer) for layer in candidate_layers) / len(candidate_layers) if candidate_layers else 0.0},
        "debug_layers": _debug_layers(trajectory, matches),
    }


def match_candidate_cost(
    trajectory: Trajectory,
    searcher: CandidateSearcher,
    graph: RoadGraph,
    k: int = 5,
) -> dict:
    matches = []
    previous: RoadCandidate | None = None
    candidate_layers = []
    for index, point in enumerate(trajectory.points):
        candidates = searcher.nearby_roads(point.coordinate, k)
        candidate_layers.append(candidates)
        if not candidates:
            continue
        heading = trajectory_heading(trajectory, index)
        scored = [
            (candidate_total_cost(graph, candidate, heading, previous), candidate)
            for candidate in candidates
        ]
        costs, best = min(scored, key=lambda item: item[0]["total_cost"])
        matches.append(_match_record(index, best, costs | {"candidate_count": len(candidates), "candidates": [candidate.to_dict() for candidate in candidates]}))
        previous = best
    return {
        "trajectory_id": trajectory.id,
        "algorithm": "candidate_cost",
        "matched_road_sequence": _dedupe_sequence([match["matched_road_id"] for match in matches]),
        "confidence": _distance_confidence(matches),
        "matches": matches,
        "metrics": {"candidate_count_avg": sum(len(layer) for layer in candidate_layers) / len(candidate_layers) if candidate_layers else 0.0},
        "debug_layers": _debug_layers(trajectory, matches),
    }


def _dedupe_sequence(road_ids: list[str]) -> list[str]:
    sequence: list[str] = []
    for road_id in road_ids:
        if not sequence or sequence[-1] != road_id:
            sequence.append(road_id)
    return sequence


def _distance_confidence(matches: list[dict]) -> float:
    if not matches:
        return 0.0
    avg = sum(match["distance"] for match in matches) / len(matches)
    return round(1.0 / (1.0 + avg / 25.0), 3)


def _debug_layers(trajectory: Trajectory, matches: list[dict]) -> dict:
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
                    "properties": {"layer": "matched_points", "point_index": match["point_index"], "road_id": match["matched_road_id"]},
                    "geometry": {"type": "Point", "coordinates": match["projection_point"]},
                }
                for match in matches
            ],
        },
    }
