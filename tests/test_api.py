from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_and_visualization_state() -> None:
    client = TestClient(app)

    health = client.get("/health")
    state = client.get("/visualization/state")

    assert health.status_code == 200
    assert health.json()["roads"] > 0
    assert state.status_code == 200
    assert state.json()["roads"]["features"]


def test_major_api_flow() -> None:
    client = TestClient(app)

    load = client.post("/datasets/load", json={"source": "sample"})
    nearby = client.get("/roads/nearby", params={"lon": 116.4015, "lat": 39.911, "k": 3})
    query = client.post(
        "/spatial/query",
        json={"query_type": "roads_in_bbox", "bbox": [116.399, 39.909, 116.411, 39.911]},
    )
    geofence = client.post("/geofence/check", json={})
    matching = client.post("/mapmatch", json={"algorithm": "hmm", "k": 5})
    route = client.post(
        "/route/shortest",
        json={
            "start": [116.390, 39.900],
            "end": [116.410, 39.920],
            "mode": "shortest_distance",
            "algorithm": "astar",
        },
    )

    assert load.status_code == 200
    assert nearby.status_code == 200
    assert query.status_code == 200
    assert geofence.status_code == 200
    assert matching.status_code == 200
    assert route.status_code == 200
    assert matching.json()["matches"]
    assert route.json()["geometry"]["coordinates"]

