from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import time
from pathlib import Path
from typing import Any, Callable

from app.core.bbox import BBox, bbox_of_coords
from app.core.geojson import feature_collection
from app.models import RoadEdge
from app.spatial_index import (
    BasicRTreeIndex,
    BruteForceIndex,
    GridIndex,
    KDTreeIndex,
    MortonIndex,
    QuadTreeIndex,
    STRRTreeIndex,
)
from app.storage.geojson_loader import load_roads_geojson

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

IndexFactory = Callable[[list[tuple[BBox, str]]], Any]


INDEX_FACTORIES: dict[str, IndexFactory] = {
    "brute": lambda items: BruteForceIndex(items),
    "brute_force": lambda items: BruteForceIndex(items),
    "grid": lambda items: GridIndex(items),
    "kdtree": lambda items: KDTreeIndex(items),
    "quadtree": lambda items: QuadTreeIndex(items),
    "rtree": lambda items: BasicRTreeIndex(items),
    "str_rtree": lambda items: STRRTreeIndex(items),
    "morton": lambda items: MortonIndex(items),
}


def run_spatial_index_benchmark(
    dataset: str = "synthetic_uniform",
    item_count: int = 1000,
    query_count: int = 50,
    index_types: list[str] | None = None,
    query_types: list[str] | None = None,
    seed: int = 7,
    radius_m: float = 150.0,
    bbox_size_m: float = 250.0,
    roads: list[RoadEdge] | None = None,
    bbox_queries: list[BBox] | None = None,
    output: str | Path | None = None,
    return_debug_layers: bool = False,
) -> dict[str, Any]:
    index_types = index_types or ["brute", "grid", "kdtree", "quadtree", "rtree", "str_rtree", "morton"]
    query_types = query_types or ["bbox", "radius", "nearest"]
    roads = list(roads) if roads is not None else make_roads(dataset, item_count, seed)
    items = [(bbox_of_coords(road.geometry), road.id) for road in roads if road.geometry]
    road_by_id = {road.id: road for road in roads}
    bounds = _bounds_from_items(items)
    queries = make_queries(bounds, query_count, seed, radius_m, bbox_size_m)
    if bbox_queries is not None:
        queries["bbox"] = bbox_queries
    brute = BruteForceIndex(items)

    results: list[dict[str, Any]] = []
    for index_type in index_types:
        factory = INDEX_FACTORIES.get(index_type)
        if factory is None:
            raise ValueError(f"Unknown spatial index type: {index_type}")
        started = time.perf_counter()
        index = factory(items)
        build_time_ms = (time.perf_counter() - started) * 1000.0
        for query_type in query_types:
            results.append(
                _benchmark_index(
                    index_type=index_type,
                    index=index,
                    brute=brute,
                    queries=queries[query_type],
                    query_type=query_type,
                    build_time_ms=build_time_ms,
                )
            )

    payload: dict[str, Any] = {
        "dataset": dataset,
        "item_count": len(items),
        "query_count": query_count,
        "query_types": query_types,
        "index_types": index_types,
        "results": results,
        "debug_layers": _debug_layers(roads, queries, road_by_id) if return_debug_layers else {},
    }
    if output is not None:
        write_benchmark_outputs(payload, output)
    return payload


def make_roads(dataset: str, count: int, seed: int = 7) -> list[RoadEdge]:
    if dataset == "osm_roads_sample":
        try:
            _nodes, roads = load_roads_geojson(DATA_DIR / "roads.geojson")
        except Exception:
            return _synthetic_uniform_roads(count, seed)
        return roads[:count] if count else roads
    if dataset == "synthetic_clustered":
        return _synthetic_clustered_roads(count, seed)
    if dataset == "synthetic_uniform":
        return _synthetic_uniform_roads(count, seed)
    raise ValueError(f"Unknown benchmark dataset: {dataset}")


def make_queries(
    bounds: BBox,
    query_count: int,
    seed: int,
    radius_m: float,
    bbox_size_m: float,
) -> dict[str, list[Any]]:
    rng = random.Random(seed + 101)
    bbox_queries: list[BBox] = []
    radius_queries: list[tuple[tuple[float, float], float]] = []
    nearest_queries: list[tuple[float, float]] = []
    min_lon, min_lat, max_lon, max_lat = bounds
    for _ in range(query_count):
        lon = rng.uniform(min_lon, max_lon)
        lat = rng.uniform(min_lat, max_lat)
        lon_delta, lat_delta = _meter_delta(lon, lat, bbox_size_m / 2.0)
        bbox_queries.append((lon - lon_delta, lat - lat_delta, lon + lon_delta, lat + lat_delta))
        radius_queries.append(((lon, lat), radius_m))
        nearest_queries.append((lon, lat))
    return {"bbox": bbox_queries, "radius": radius_queries, "nearest": nearest_queries}


def write_benchmark_outputs(payload: dict[str, Any], output: str | Path) -> None:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_path = output_path.with_suffix(".md")
    markdown_path.write_text(render_markdown_report(payload), encoding="utf-8")


def render_markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Spatial Index Benchmark",
        "",
        f"- Dataset: `{payload['dataset']}`",
        f"- Items: `{payload['item_count']}`",
        f"- Queries per type: `{payload['query_count']}`",
        "",
        "| Index | Query | Build ms | p50 ms | p95 ms | p99 ms | Avg candidates | Recall | False positive | Memory bytes |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["results"]:
        lines.append(
            "| {index} | {query_type} | {build_time_ms:.3f} | {p50_ms:.4f} | {p95_ms:.4f} | "
            "{p99_ms:.4f} | {avg_candidate_count:.2f} | {recall:.3f} | "
            "{false_positive_rate:.3f} | {memory_estimate_bytes} |".format(**row)
        )
    lines.extend(
        [
            "",
            "Recall is measured against brute force. False positives are allowed for prefilter indexes, but exact filters here keep them near zero.",
        ]
    )
    return "\n".join(lines) + "\n"


def _benchmark_index(
    index_type: str,
    index: Any,
    brute: BruteForceIndex[str],
    queries: list[Any],
    query_type: str,
    build_time_ms: float,
) -> dict[str, Any]:
    latencies: list[float] = []
    candidate_total = 0
    false_positive_total = 0
    expected_total = 0
    hit_total = 0
    for query in queries:
        expected = _run_query(brute, query_type, query)
        started = time.perf_counter()
        actual = _run_query(index, query_type, query)
        latencies.append((time.perf_counter() - started) * 1000.0)
        expected_set = set(expected)
        actual_set = set(actual)
        candidate_total += len(actual)
        false_positive_total += len(actual_set - expected_set)
        expected_total += len(expected_set)
        hit_total += len(actual_set & expected_set)
    stats = index.stats() if hasattr(index, "stats") else {}
    return {
        "index": index_type,
        "query_type": query_type,
        "build_time_ms": build_time_ms,
        "query_count": len(queries),
        "p50_ms": _percentile(latencies, 0.50),
        "p95_ms": _percentile(latencies, 0.95),
        "p99_ms": _percentile(latencies, 0.99),
        "max_ms": max(latencies) if latencies else 0.0,
        "avg_candidate_count": candidate_total / max(1, len(queries)),
        "false_positive_rate": false_positive_total / max(1, candidate_total),
        "recall": 1.0 if expected_total == 0 else hit_total / expected_total,
        "memory_estimate_bytes": int(stats.get("memory_estimate_bytes", 0)),
        "index_stats": stats,
    }


def _run_query(index: Any, query_type: str, query: Any) -> list[str]:
    if query_type == "bbox":
        return index.query_bbox(query)
    if query_type == "radius":
        point, radius_m = query
        return index.query_radius(point, radius_m)
    if query_type == "nearest":
        return index.nearest(query, k=3)
    raise ValueError(f"Unknown query type: {query_type}")


def _synthetic_uniform_roads(count: int, seed: int) -> list[RoadEdge]:
    rng = random.Random(seed)
    roads: list[RoadEdge] = []
    for index in range(count):
        lon = 116.0 + rng.random() * 0.12
        lat = 39.0 + rng.random() * 0.12
        angle = rng.random() * math.tau
        length_m = rng.uniform(40.0, 180.0)
        d_lon, d_lat = _meter_delta(lon, lat, length_m)
        end = (lon + math.cos(angle) * d_lon, lat + math.sin(angle) * d_lat)
        roads.append(
            RoadEdge(
                id=f"uniform_{index}",
                from_node=f"u_{index}_a",
                to_node=f"u_{index}_b",
                geometry=[(lon, lat), end],
                length=length_m,
                road_class="local",
            )
        )
    return roads


def _synthetic_clustered_roads(count: int, seed: int) -> list[RoadEdge]:
    rng = random.Random(seed)
    centers = [(116.02, 39.02), (116.06, 39.07), (116.10, 39.04), (116.04, 39.10)]
    roads: list[RoadEdge] = []
    for index in range(count):
        center = centers[index % len(centers)]
        lon = center[0] + rng.gauss(0.0, 0.006)
        lat = center[1] + rng.gauss(0.0, 0.006)
        angle = rng.choice([0.0, math.pi / 2.0, math.pi / 4.0, -math.pi / 4.0]) + rng.gauss(0.0, 0.08)
        length_m = rng.uniform(35.0, 220.0)
        d_lon, d_lat = _meter_delta(lon, lat, length_m)
        end = (lon + math.cos(angle) * d_lon, lat + math.sin(angle) * d_lat)
        roads.append(
            RoadEdge(
                id=f"clustered_{index}",
                from_node=f"c_{index}_a",
                to_node=f"c_{index}_b",
                geometry=[(lon, lat), end],
                length=length_m,
                road_class="collector" if index % 5 == 0 else "local",
            )
        )
    return roads


def _bounds_from_items(items: list[tuple[BBox, str]]) -> BBox:
    if not items:
        return (116.0, 39.0, 116.01, 39.01)
    return (
        min(item[0][0] for item in items),
        min(item[0][1] for item in items),
        max(item[0][2] for item in items),
        max(item[0][3] for item in items),
    )


def _meter_delta(lon: float, lat: float, meters: float) -> tuple[float, float]:
    del lon
    lat_delta = meters / 111_320.0
    lon_scale = max(0.1, abs(math.cos(math.radians(lat))))
    lon_delta = meters / (111_320.0 * lon_scale)
    return lon_delta, lat_delta


def _debug_layers(roads: list[RoadEdge], queries: dict[str, list[Any]], road_by_id: dict[str, RoadEdge]) -> dict[str, Any]:
    sample_roads = roads[: min(100, len(roads))]
    query_bbox = queries["bbox"][0] if queries["bbox"] else None
    bbox_features = []
    if query_bbox is not None:
        bbox_features.append(_bbox_feature(query_bbox, {"layer": "sample_bbox_query"}))
    centers = []
    if queries["nearest"]:
        point = queries["nearest"][0]
        centers.append(
            {
                "type": "Feature",
                "properties": {"layer": "sample_nearest_query"},
                "geometry": {"type": "Point", "coordinates": [point[0], point[1]]},
            }
        )
    del road_by_id
    return {
        "items_sample": feature_collection(road.to_geojson_feature() for road in sample_roads),
        "sample_bbox_query": feature_collection(bbox_features),
        "sample_points": feature_collection(centers),
    }


def _bbox_feature(bbox: BBox, properties: dict[str, Any]) -> dict[str, Any]:
    min_lon, min_lat, max_lon, max_lat = bbox
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [min_lon, min_lat],
                    [max_lon, min_lat],
                    [max_lon, max_lat],
                    [min_lon, max_lat],
                    [min_lon, min_lat],
                ]
            ],
        },
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    index = min(len(values) - 1, max(0, round((len(values) - 1) * percentile)))
    return values[index]


def timed(index: Any, query_bbox: BBox, iterations: int) -> dict[str, float]:
    latencies: list[float] = []
    count = 0
    for _ in range(iterations):
        started = time.perf_counter()
        count = len(index.query(query_bbox))
        latencies.append((time.perf_counter() - started) * 1000.0)
    return {
        "candidate_count": float(count),
        "p50": statistics.median(latencies),
        "p95": _percentile(latencies, 0.95),
        "p99": _percentile(latencies, 0.99),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run HDMap-Lab spatial index benchmark v2.")
    parser.add_argument("--dataset", default="synthetic_uniform", choices=["synthetic_uniform", "synthetic_clustered", "osm_roads_sample"])
    parser.add_argument("--items", type=int, default=10_000)
    parser.add_argument("--queries", type=int, default=1000)
    parser.add_argument("--indexes", default="brute,grid,kdtree,quadtree,rtree,str_rtree,morton")
    parser.add_argument("--query-types", default="bbox,radius,nearest")
    parser.add_argument("--radius-m", type=float, default=150.0)
    parser.add_argument("--bbox-size-m", type=float, default=250.0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output", default="docs/assets/spatial_index_benchmark.json")
    args = parser.parse_args()

    payload = run_spatial_index_benchmark(
        dataset=args.dataset,
        item_count=args.items,
        query_count=args.queries,
        index_types=_parse_csv(args.indexes),
        query_types=_parse_csv(args.query_types),
        seed=args.seed,
        radius_m=args.radius_m,
        bbox_size_m=args.bbox_size_m,
        output=args.output,
        return_debug_layers=True,
    )
    print(f"dataset={payload['dataset']} items={payload['item_count']} queries={payload['query_count']}")
    for row in payload["results"]:
        print(
            f"{row['index']} {row['query_type']}: p95={row['p95_ms']:.4f}ms "
            f"recall={row['recall']:.3f} fp={row['false_positive_rate']:.3f}"
        )
    print(f"wrote {args.output} and {Path(args.output).with_suffix('.md')}")


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    main()
