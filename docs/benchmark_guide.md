# Benchmark Guide

HDMap-Lab benchmarks are designed for local, reproducible algorithm inspection. They should not be read as production performance claims unless the dataset, machine, query distribution, and generated reports are included.

## How To Run

Spatial index benchmark:

```bash
python -m benchmarks.spatial_index_benchmark
```

Optional parameters:

```bash
python -m benchmarks.spatial_index_benchmark --dataset synthetic_clustered --items 10000 --queries 1000 --output docs/assets/spatial_index_benchmark.json
```

Map matching benchmark:

```bash
python -m benchmarks.map_matching_benchmark
```

Topology repair benchmark:

```bash
python -m benchmarks.topology_repair_benchmark
```

City-scale local-data generator:

```bash
python -m benchmarks.city_scale_benchmark --roads data/roads.geojson --queries 100 --output docs/city_scale_benchmark_result.md
```

The city-scale script can run against any local road GeoJSON extract with LineString features. Do not commit or claim city-scale numbers unless the input dataset is documented.

## How To Prepare Data

For synthetic tests, no external data is required.

For local GeoJSON road data:

1. Prepare a FeatureCollection where road geometries are LineString features.
2. Keep the coordinate system assumption clear. The current project is optimized for small-area lon/lat road-network experiments.
3. Record road count, bbox, query count, and any filtering step used before running a benchmark.

For OSM samples:

```bash
python -m scripts.download_osm_sample --place "Tsinghua University, Beijing"
```

Large extracts should stay out of git unless they are intentionally small fixtures.

## How To Interpret p50 / p95 / p99

- `p50`: median latency. Half of queries are faster than this value.
- `p95`: tail latency for most interactive workloads. A useful signal for UI/API responsiveness.
- `p99`: extreme tail latency. Sensitive to GC, OS scheduling, and outlier query shapes.

Always compare p50/p95/p99 with the same query set and same data. A faster p50 with poor recall is not a valid win.

## Correctness Checks

Spatial index correctness is measured against brute force:

- `recall = matched_expected_hits / expected_hits`
- `false_positive_rate = extra_candidates / returned_candidates`
- A correctness-passing exact index should report recall `1.0` for bbox queries.

Map matching correctness is measured against synthetic ground-truth road sequences:

- sequence accuracy
- precision / recall / F1
- edit distance
- illegal transition count
- candidate count average

Topology repair correctness is evaluated with before/after issue summaries:

- duplicate edges removed
- illegal crossings repaired
- quality score not degraded
- operation log and debug layers returned

## How To Avoid Misreading Benchmarks

- Do not compare toy/synthetic benchmark numbers to city-scale production systems.
- Do not report only latency. Include recall/correctness checks.
- Do not hide data size or query count.
- Do not claim PostGIS superiority or inferiority from a tiny sample.
- Do not claim full city-scale results unless the generated JSON/Markdown report is produced from a real local extract.
- Treat Python in-memory indexes as algorithm demonstrations unless production deployment work is separately done.
