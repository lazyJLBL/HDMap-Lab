from __future__ import annotations

import random
import statistics
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.bbox import bbox_of_coords
from app.models import RoadEdge
from app.spatial_index import BasicRTreeIndex, BruteForceIndex, GridIndex, QuadTreeIndex, STRRTreeIndex


def make_roads(size: int) -> list[RoadEdge]:
    roads: list[RoadEdge] = []
    for index in range(size):
        x = index % 100
        y = index // 100
        lon = 116.0 + x * 0.001
        lat = 39.0 + y * 0.001
        roads.append(
            RoadEdge(
                id=f"edge_{index}",
                from_node=f"n_{index}_a",
                to_node=f"n_{index}_b",
                geometry=[(lon, lat), (lon + 0.0008, lat + 0.0002)],
                length=90.0,
            )
        )
    return roads


def timed(index, query_bbox: tuple[float, float, float, float], iterations: int) -> dict:
    latencies: list[float] = []
    count = 0
    for _ in range(iterations):
        started = time.perf_counter()
        count = len(index.query(query_bbox))
        latencies.append((time.perf_counter() - started) * 1000.0)
    return {
        "candidate_count": count,
        "p50": statistics.median(latencies),
        "p95": percentile(latencies, 0.95),
        "p99": percentile(latencies, 0.99),
    }


def percentile(values: list[float], q: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, round((len(values) - 1) * q))]


def main() -> None:
    random.seed(7)
    roads = make_roads(5_000)
    items = [(bbox_of_coords(road.geometry), road.id) for road in roads]
    query_bbox = (116.020, 39.010, 116.055, 39.040)
    print("| Index | Build ms | Candidates | p50 ms | p95 ms | p99 ms |")
    print("| --- | ---: | ---: | ---: | ---: | ---: |")
    for label, factory in [
        ("brute force", lambda: BruteForceIndex(items)),
        ("grid", lambda: GridIndex(items)),
        ("quadtree", lambda: QuadTreeIndex(items)),
        ("R-tree", lambda: BasicRTreeIndex(items)),
        ("STR R-tree", lambda: STRRTreeIndex(items)),
    ]:
        started = time.perf_counter()
        index = factory()
        build_ms = (time.perf_counter() - started) * 1000.0
        stats = timed(index, query_bbox, 100)
        print(
            f"| {label} | {build_ms:.3f} | {stats['candidate_count']} | "
            f"{stats['p50']:.3f} | {stats['p95']:.3f} | {stats['p99']:.3f} |"
        )


if __name__ == "__main__":
    main()
