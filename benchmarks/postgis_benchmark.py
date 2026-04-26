from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.bbox import bbox_of_coords
from app.spatial_index import STRRTreeIndex

DEFAULT_DSN = "postgresql://hdmap:hdmap@127.0.0.1:5432/hdmap_lab"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare HDMap-Lab STR R-tree with PostGIS GiST.")
    parser.add_argument("--roads", default="data/roads.geojson")
    parser.add_argument("--dsn", default=os.getenv("HDMAP_POSTGIS_DSN", DEFAULT_DSN))
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--bbox", nargs=4, type=float, default=[116.399, 39.909, 116.411, 39.911])
    args = parser.parse_args()

    collection = json.loads(Path(args.roads).read_text(encoding="utf-8"))
    features = [feature for feature in collection.get("features", []) if (feature.get("geometry") or {}).get("type") == "LineString"]
    local_result = benchmark_local(features, tuple(args.bbox), args.iterations)
    postgis_result = benchmark_postgis(features, tuple(args.bbox), args.iterations, args.dsn)

    print("| Engine | Build/Load ms | Count | p50 ms | p95 ms | p99 ms |")
    print("| --- | ---: | ---: | ---: | ---: | ---: |")
    for row in [local_result, postgis_result]:
        print(
            f"| {row['engine']} | {row['build_ms']:.3f} | {row['count']} | "
            f"{row['p50_ms']:.3f} | {row['p95_ms']:.3f} | {row['p99_ms']:.3f} |"
        )


def benchmark_local(features: list[dict[str, Any]], bbox: tuple[float, float, float, float], iterations: int) -> dict[str, Any]:
    items = []
    for index, feature in enumerate(features):
        coords = [tuple(coord) for coord in feature["geometry"]["coordinates"]]
        road_id = str(feature.get("id") or (feature.get("properties") or {}).get("id") or index)
        items.append((bbox_of_coords(coords), road_id))
    started = time.perf_counter()
    index = STRRTreeIndex(items)
    build_ms = (time.perf_counter() - started) * 1000.0
    latencies: list[float] = []
    count = 0
    for _ in range(iterations):
        query_started = time.perf_counter()
        count = len(index.query(bbox))
        latencies.append((time.perf_counter() - query_started) * 1000.0)
    return _row("HDMap STR R-tree", build_ms, count, latencies)


def benchmark_postgis(
    features: list[dict[str, Any]],
    bbox: tuple[float, float, float, float],
    iterations: int,
    dsn: str,
) -> dict[str, Any]:
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("psycopg is required: python -m pip install 'psycopg[binary]'") from exc

    started = time.perf_counter()
    try:
        conn_context = psycopg.connect(dsn, connect_timeout=5)
    except psycopg.OperationalError as exc:
        raise SystemExit(f"PostGIS is not reachable. Start it with `docker compose up -d postgis`. Details: {exc}") from exc

    with conn_context as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
            cur.execute("DROP TABLE IF EXISTS hdmap_lab_benchmark_roads")
            cur.execute(
                """
                CREATE TABLE hdmap_lab_benchmark_roads (
                    id text PRIMARY KEY,
                    geom geometry(LineString, 4326) NOT NULL
                )
                """
            )
            rows = [
                (
                    str(feature.get("id") or (feature.get("properties") or {}).get("id") or index),
                    json.dumps(feature["geometry"]),
                )
                for index, feature in enumerate(features)
            ]
            cur.executemany(
                "INSERT INTO hdmap_lab_benchmark_roads(id, geom) VALUES (%s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))",
                rows,
            )
            cur.execute("CREATE INDEX hdmap_lab_benchmark_roads_gix ON hdmap_lab_benchmark_roads USING GIST (geom)")
            cur.execute("ANALYZE hdmap_lab_benchmark_roads")
        conn.commit()
        build_ms = (time.perf_counter() - started) * 1000.0

        latencies: list[float] = []
        count = 0
        min_lon, min_lat, max_lon, max_lat = bbox
        with conn.cursor() as cur:
            for _ in range(iterations):
                query_started = time.perf_counter()
                cur.execute(
                    """
                    SELECT count(*)
                    FROM hdmap_lab_benchmark_roads
                    WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                      AND ST_Intersects(geom, ST_MakeEnvelope(%s, %s, %s, %s, 4326))
                    """,
                    (min_lon, min_lat, max_lon, max_lat, min_lon, min_lat, max_lon, max_lat),
                )
                count = int(cur.fetchone()[0])
                latencies.append((time.perf_counter() - query_started) * 1000.0)
    return _row("PostGIS GiST", build_ms, count, latencies)


def _row(engine: str, build_ms: float, count: int, latencies: list[float]) -> dict[str, Any]:
    return {
        "engine": engine,
        "build_ms": build_ms,
        "count": count,
        "p50_ms": statistics.median(latencies),
        "p95_ms": _percentile(latencies, 0.95),
        "p99_ms": _percentile(latencies, 0.99),
    }


def _percentile(values: list[float], q: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, round((len(values) - 1) * q))]


if __name__ == "__main__":
    main()
