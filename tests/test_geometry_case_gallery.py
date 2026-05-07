from __future__ import annotations

from fastapi.testclient import TestClient

from app.geometry_kernel.case_gallery import load_geometry_cases, run_all_geometry_cases, run_geometry_case
from app.main import app


def test_geometry_cases_load_with_expected_fields() -> None:
    cases = load_geometry_cases()
    assert len(cases) >= 15
    for case in cases:
        assert case["id"]
        assert case["category"] in {"predicate", "intersection", "polygon", "polyline", "topology"}
        assert case["expected"]
        assert case["debug_geojson"]["type"] == "FeatureCollection"


def test_run_all_geometry_cases_pass_rate() -> None:
    payload = run_all_geometry_cases()
    assert payload["summary"]["total"] >= 15
    assert payload["summary"]["pass_rate"] >= 0.95
    assert payload["summary"]["failed"] == 0


def test_self_intersecting_bowtie_case() -> None:
    case = next(case for case in load_geometry_cases() if case["id"] == "self_intersecting_bowtie_polygon")
    result = run_geometry_case(case)
    assert result["passed"]
    assert result["actual"]["self_intersection_count"] == 1
    assert result["actual"]["point"] == [1.0, 1.0]


def test_overlapping_segment_case() -> None:
    case = next(case for case in load_geometry_cases() if case["id"] == "overlapping_segments")
    result = run_geometry_case(case)
    assert result["passed"]
    assert result["actual"]["kind"] == "overlap"
    assert result["actual"]["overlap"] == [[1.0, 0.0], [3.0, 0.0]]


def test_geometry_case_api() -> None:
    client = TestClient(app)
    cases = client.get("/geometry/cases")
    run_one = client.post("/geometry/cases/run", json={"case_id": "t_junction_segments"})
    run_all = client.post("/geometry/cases/run-all")

    assert cases.status_code == 200
    assert run_one.status_code == 200
    assert run_all.status_code == 200
    assert cases.json()["metrics"]["total"] >= 15
    assert run_one.json()["data"]["passed"]
    assert run_all.json()["metrics"]["failed"] == 0
