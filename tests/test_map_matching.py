from __future__ import annotations

from app.map_matching import match_candidate_cost, match_hmm, match_nearest


def test_nearest_map_matching(runtime) -> None:
    trajectory = runtime.get_trajectory("traj_001")
    assert trajectory is not None
    result = match_nearest(trajectory, runtime.candidate_searcher, 5)

    assert result["algorithm"] == "nearest"
    assert result["matches"]
    assert result["matched_road_sequence"]


def test_candidate_cost_and_hmm_map_matching(runtime) -> None:
    trajectory = runtime.get_trajectory("traj_001")
    assert trajectory is not None

    cost_result = match_candidate_cost(trajectory, runtime.candidate_searcher, runtime.graph, 5)
    hmm_result = match_hmm(trajectory, runtime.candidate_searcher, runtime.graph, 5)

    assert cost_result["algorithm"] == "candidate_cost"
    assert hmm_result["algorithm"] == "hmm"
    assert cost_result["confidence"] > 0
    assert hmm_result["confidence"] > 0

