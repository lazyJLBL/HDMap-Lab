from __future__ import annotations

from app.core.geojson import normalize_polygon
from app.storage.osm_loader import load_osm_file


def test_nearby_roads_uses_indexes(runtime) -> None:
    assert runtime.candidate_searcher is not None
    candidates = runtime.candidate_searcher.nearby_roads((116.4015, 39.9110), 3)

    assert len(candidates) == 3
    assert candidates[0].distance < 200


def test_roads_in_bbox(runtime) -> None:
    roads = runtime.roads_in_bbox((116.399, 39.909, 116.411, 39.911))

    assert {road.id for road in roads} >= {"edge_h_11_21"}


def test_points_in_polygon(runtime) -> None:
    polygon = normalize_polygon(
        [
            [
                [116.398, 39.908],
                [116.406, 39.908],
                [116.406, 39.916],
                [116.398, 39.916],
                [116.398, 39.908],
            ]
        ]
    )

    points = runtime.points_in_polygon(polygon)

    assert points
    assert all("trajectory_id" in point for point in points)


def test_osm_file_loader(sample_data_dir) -> None:
    nodes, roads = load_osm_file(sample_data_dir / "sample.osm")

    assert len(nodes) == 4
    assert len(roads) == 3
    assert roads[0].length > 0
