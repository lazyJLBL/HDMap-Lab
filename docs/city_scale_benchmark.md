# City-Scale Benchmark

The city-scale benchmark is intentionally data-driven. Large OSM extracts are not committed to git; keep them under `datasets/osm_samples/` and run:

```bash
python -m benchmarks.city_scale_benchmark \
  --roads datasets/osm_samples/sample.geojson \
  --queries 500 \
  --output docs/city_scale_benchmark_result.md
```

The report includes:

- road count
- dataset bbox
- total road length
- query count
- build time
- memory delta
- mean candidate count
- p50 / p95 / p99 query latency

For a local smoke test, run it against the built-in data:

```bash
python -m benchmarks.city_scale_benchmark --roads data/roads.geojson --queries 20
```
