from __future__ import annotations

from app.map_matching.candidate_search import CandidateSearcher
from app.map_matching.synthetic import SUPPORTED_CASES, generate_all_synthetic_cases, generate_synthetic_case


def test_all_synthetic_cases_generate_required_fields() -> None:
    cases = generate_all_synthetic_cases()
    assert {case.case_id for case in cases} == set(SUPPORTED_CASES)
    for case in cases:
        payload = case.to_dict()
        assert payload["case_id"]
        assert payload["roads"]
        assert payload["trajectory"]
        assert payload["ground_truth_road_sequence"]
        assert payload["noise_config"] is not None
        assert payload["debug_layers"]["roads"]["type"] == "FeatureCollection"


def test_candidate_search_filters_and_debug_layers() -> None:
    case = generate_synthetic_case("straight_clean")
    searcher = CandidateSearcher(case.roads)
    point = case.trajectory.points[0].coordinate
    candidates = searcher.search(point, radius_m=50.0, k=5, road_class_filter={"primary"}, layer_filter={0})

    assert candidates
    assert all(candidate.road_class == "primary" for candidate in candidates)
    assert all(candidate.layer == 0 for candidate in candidates)
    assert {"distance_m", "heading_diff", "road_class", "layer", "oneway"} <= set(candidates[0].score_features)
    debug_layers = searcher.candidate_debug_layers(point, candidates)
    assert debug_layers["candidate_roads"]["features"]
