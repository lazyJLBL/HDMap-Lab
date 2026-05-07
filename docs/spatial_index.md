# Spatial Index Benchmark v2

HDMap-Lab uses in-memory spatial indexes as an engineering experiment bench for road-network queries. The goal is not to replace PostGIS, but to make the candidate generation, recall, false positives, and tail latency visible.

## Unified Interface

Every bbox-based index implements:

```python
index.build(items)
index.query_bbox((min_lon, min_lat, max_lon, max_lat))
index.query_radius((lon, lat), radius_m=100)
index.nearest((lon, lat), k=3)
index.stats()
```

Items are `(bbox, id)` pairs. The old `query(bbox)` method is still available for compatibility.

## Implementations

| Index | Strength | Weakness |
| --- | --- | --- |
| BruteForceIndex | Exact baseline; simple correctness oracle | O(n) for every query |
| GridIndex | Good for uniformly distributed roads and fixed-radius lookup | Cell size is sensitive; clustered data can overload cells |
| KDTreeIndex | Good for point nearest-neighbor over bbox centroids | Not a natural rectangle index; bbox queries require exact scan |
| QuadTreeIndex | Adaptive subdivision for mixed density | Can degenerate when many long/overlapping bboxes cross quadrants |
| RTreeIndex | Hierarchical bbox pruning | Simple packed tree here, no dynamic insert/delete optimization |
| STRRTreeIndex | Sort-tile-recursive bulk loading improves static query locality | Static only; rebuild required after large updates |
| MortonIndex | Z-order sorting exposes cache-friendly spatial locality | Current query path uses exact filtering after Morton sort |

## Benchmark Data

The v2 benchmark supports:

- `synthetic_uniform`: random short road segments across a uniform extent.
- `synthetic_clustered`: roads clustered around several centers to test overloaded cells and tree balance.
- `osm_roads_sample`: loads `data/roads.geojson` as a small OSM-like sample, with synthetic fallback if the file is unavailable.

For each dataset it generates bbox, radius, and nearest queries. All outputs are checked against `BruteForceIndex`.

## Metrics

Each index/query row reports:

- `build_time_ms`
- `p50_ms`, `p95_ms`, `p99_ms`, `max_ms`
- `avg_candidate_count`
- `false_positive_rate`
- `recall`
- `memory_estimate_bytes`
- `index_stats`

`recall == 1.0` means the index did not miss any brute-force result. `false_positive_rate` is the share of returned candidates that brute force did not consider exact matches. Spatial prefilters can legally have false positives, but false negatives are unacceptable for candidate generation.

Tail latency matters because a map-matching or routing workflow usually performs many small spatial queries. A low average can hide overloaded grid cells or unbalanced tree branches; `p95` and `p99` show those worst-case query paths.

## Complexity

| Query | Brute force | Grid | KD-tree bbox | Quadtree | R-tree / STR R-tree | Morton |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Build | O(n) | O(n * touched_cells) | O(n log n) | O(n log n) avg | O(n log n) | O(n log n) |
| BBox query | O(n) | O(c + k) avg | O(n) | O(log n + k) avg | O(log n + k) avg | O(n) currently |
| Radius query | O(n) exact | bbox prefilter + exact distance | O(n) exact | bbox prefilter + exact distance | bbox prefilter + exact distance | O(n) currently |
| Nearest | O(n log n) here | O(n log n) here | O(n log n) exact fallback | O(n log n) here | O(n log n) here | O(n log n) here |

`k` is candidate count and `c` is the number of touched cells. The current KDTree and Morton indexes are included to show design tradeoffs, not because they are the best bbox query structures.

## CLI

```bash
python -m benchmarks.spatial_index_benchmark \
  --dataset synthetic_clustered \
  --items 10000 \
  --queries 1000 \
  --indexes brute,grid,kdtree,quadtree,rtree,str_rtree,morton \
  --output docs/assets/spatial_index_benchmark.json
```

The command writes:

- `docs/assets/spatial_index_benchmark.json`
- `docs/assets/spatial_index_benchmark.md`

## API

`POST /benchmarks/spatial-index`

```json
{
  "dataset": "synthetic_clustered",
  "index_types": ["brute", "grid", "quadtree", "rtree", "str_rtree"],
  "query_types": ["bbox", "radius", "nearest"],
  "query_count": 100,
  "seed": 7,
  "radius_m": 150,
  "bbox_size_m": 250,
  "return_debug_layers": true
}
```

The response contains `results`, aggregate metrics, and optional debug layers with sample road features and sample query geometries for frontend rendering.

## Current Limits

- Coordinates are treated with local meter approximations; this is acceptable for city-scale experiments but not global geodesy.
- KDTreeIndex uses bbox centroid logic and exact fallback for correctness, so it is not optimized for rectangle intersection.
- MortonIndex currently sorts by Z-order code but still exact-filters all entries; a production version would range-scan code intervals.
- Dynamic updates are not optimized. STR R-tree and Morton indexes are static bulk-loaded structures.
