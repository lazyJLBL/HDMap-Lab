from __future__ import annotations

import random
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.bbox import bbox_of_coords
from app.core.geometry import point_to_polyline_distance
from app.index.kdtree import KDTree
from app.index.rtree import RTreeIndex
from app.map_matching.candidate_search import CandidateSearcher, road_bbox_items, road_centroid_items
from app.models import RoadEdge


def make_roads(size: int) -> list[RoadEdge]:
    roads: list[RoadEdge] = []
    for index in range(size):
        x = index % 100
        y = index // 100
        lon = 116.0 + x * 0.001
        lat = 39.0 + y * 0.001
        coords = [(lon, lat), (lon + 0.0008, lat + 0.0002)]
        roads.append(
            RoadEdge(
                id=f"edge_{index}",
                from_node=f"n_{index}_a",
                to_node=f"n_{index}_b",
                geometry=coords,
                length=90.0,
            )
        )
    return roads


def brute_nearby(roads: list[RoadEdge], point: tuple[float, float], k: int) -> list[str]:
    scored = [(point_to_polyline_distance(point, road.geometry).distance, road.id) for road in roads]
    scored.sort()
    return [road_id for _, road_id in scored[:k]]


def brute_bbox(roads: list[RoadEdge], query: tuple[float, float, float, float]) -> list[str]:
    min_lon, min_lat, max_lon, max_lat = query
    results: list[str] = []
    for road in roads:
        bbox = bbox_of_coords(road.geometry)
        if not (bbox[2] < min_lon or bbox[0] > max_lon or bbox[3] < min_lat or bbox[1] > max_lat):
            results.append(road.id)
    return results


def timed(label: str, func):
    started = time.perf_counter()
    result = func()
    elapsed_ms = (time.perf_counter() - started) * 1000
    return label, elapsed_ms, len(result)


def main() -> None:
    random.seed(7)
    roads = make_roads(5_000)
    rtree = RTreeIndex(road_bbox_items(roads))
    kdtree = KDTree(road_centroid_items(roads))
    searcher = CandidateSearcher(roads, rtree, kdtree)
    point = (116.045, 39.024)
    query_bbox = (116.020, 39.010, 116.055, 39.040)

    rows = [
        timed("brute bbox", lambda: brute_bbox(roads, query_bbox)),
        timed("rtree bbox", lambda: rtree.query(query_bbox)),
        timed("brute nearby", lambda: brute_nearby(roads, point, 5)),
        timed("indexed nearby", lambda: searcher.nearby_roads(point, 5)),
    ]

    print("| Scenario | Time ms | Results |")
    print("| --- | ---: | ---: |")
    for label, elapsed_ms, count in rows:
        print(f"| {label} | {elapsed_ms:.3f} | {count} |")


if __name__ == "__main__":
    main()
