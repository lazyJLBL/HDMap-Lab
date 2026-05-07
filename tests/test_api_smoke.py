from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_reports_loaded_sample_network() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["roads"] > 0
    assert payload["nodes"] > 0


def test_topology_validate_and_repair_endpoints_return_debug_layers() -> None:
    client = TestClient(app)

    validate = client.post("/topology/validate", json={"return_debug_layers": True})
    repair = client.post("/topology/repair", json={"snap_tolerance_m": 1.0, "apply": False})

    assert validate.status_code == 200
    assert repair.status_code == 200
    assert validate.json()["status"] == "ok"
    assert "summary" in validate.json()["data"]
    assert repair.json()["data"]["fixed_roads"]["type"] == "FeatureCollection"


def test_spatial_benchmark_endpoint_runs_correctness_checked_indexes() -> None:
    client = TestClient(app)

    response = client.post(
        "/benchmarks/spatial-index",
        json={"iterations": 2, "query_count": 2, "index_types": ["brute", "grid", "rtree"], "query_types": ["bbox"]},
    )

    assert response.status_code == 200
    rows = response.json()["data"]["results"]
    assert {row["index"] for row in rows} == {"brute", "grid", "rtree"}
    assert all(row["recall"] == 1.0 for row in rows)


def test_map_matching_endpoint_returns_hmm_matches() -> None:
    client = TestClient(app)

    response = client.post("/mapmatch", json={"algorithm": "hmm", "k": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["algorithm"] == "hmm"
    assert payload["matches"]
    assert payload["matched_road_sequence"]


def test_routing_endpoint_returns_route_geometry() -> None:
    client = TestClient(app)

    response = client.post(
        "/route/shortest",
        json={
            "start": [116.390, 39.900],
            "end": [116.410, 39.920],
            "mode": "shortest_distance",
            "algorithm": "astar",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["algorithm"] == "astar"
    assert payload["geometry"]["type"] == "LineString"
    assert len(payload["geometry"]["coordinates"]) >= 2
