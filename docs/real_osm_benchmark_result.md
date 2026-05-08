# Real OSM / GeoJSON Benchmark Result

This report is intentionally conservative. The committed result uses the local `data/roads.geojson` demo extract because no large real OSM city extract is committed to the repository. It is a toy/local sample and does not represent city-level performance.

To reproduce with a real extract:

```bash
python -m scripts.prepare_osm_extract --input-osm path/to/extract.osm --output datasets/osm_samples/prepared_roads.geojson
python -m benchmarks.spatial_index_benchmark --dataset osm_roads_sample --items 100000 --queries 1000 --indexes brute_force,grid,quadtree,rtree,str_rtree,kdtree --query-types bbox --output docs/assets/real_osm_spatial_index_benchmark.json
```

## Dataset

- Data source: `data/roads.geojson` via `scripts.prepare_osm_extract --input-geojson`
- Road segments: 13
- BBox: `[116.39, 39.9, 116.41, 39.92]`
- Total length: 13,190.69 m
- Query count: 100 bbox queries
- Hardware environment: Windows 11 10.0.26100, Intel64 Family 6 Model 183 Stepping 1, 32 logical CPUs
- Python: 3.12.7, Anaconda build, MSC v.1929 64-bit

## Results

| Index | Build ms | Memory bytes | Mean candidates | p50 ms | p95 ms | p99 ms | Recall | False positive | Correctness |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| brute_force | 0.004 | 1248 | 0.77 | 0.0012 | 0.0015 | 0.0022 | 1.000 | 0.000 | pass |
| grid | 0.060 | 1248 | 0.77 | 0.0017 | 0.0027 | 0.0041 | 1.000 | 0.000 | pass |
| quadtree | 0.036 | 1248 | 0.77 | 0.0020 | 0.0033 | 0.0541 | 1.000 | 0.000 | pass |
| rtree | 0.042 | 1248 | 0.77 | 0.0012 | 0.0018 | 0.0021 | 1.000 | 0.000 | pass |
| str_rtree | 0.023 | 1248 | 0.77 | 0.0012 | 0.0018 | 0.0020 | 1.000 | 0.000 | pass |
| kdtree | 0.027 | 1248 | 0.77 | 0.0011 | 0.0013 | 0.0014 | 1.000 | 0.000 | pass |

Correctness is measured against brute-force bbox query results for the same sampled queries. The benchmark JSON and generated table live in:

- `docs/assets/real_osm_extract_summary.json`
- `docs/assets/real_osm_spatial_index_benchmark.json`
- `docs/assets/real_osm_spatial_index_benchmark.md`

## Interpretation

The committed sample proves the benchmark path is executable and correctness-checked. It does not prove large-city performance. For resume or interview discussion, describe this as a city-scale-capable benchmark generator with a reproducible local report, then bring a separately generated real extract report if available.
