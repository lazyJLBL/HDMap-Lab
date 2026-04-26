# Spatial Index

HDMap-Lab uses lightweight in-memory indexes after loading roads from SQLite. The goal is to avoid scanning every road for each spatial query or GPS point.

The upgraded `app/spatial_index/` package provides a common interface for:

- brute force
- grid index
- KD-tree nearest lookup
- quadtree
- basic R-tree
- STR bulk-loaded R-tree

## Why Spatial Indexing

A road network can contain thousands or millions of road segments. A brute-force nearby-road query must compute point-to-polyline distance for every segment, which is expensive and unnecessary. Spatial indexes reduce the candidate set before exact geometry calculation.

## R-Tree Usage

The R-Tree stores each road edge by its bounding box:

```text
RoadEdge geometry -> bbox(min_lon, min_lat, max_lon, max_lat) -> R-Tree
```

Used by:

- roads in bbox query
- roads in polygon query prefilter
- map matching candidate prefilter around GPS points

Query flow:

```text
query bbox -> R-Tree bbox intersection -> candidate road ids -> exact geometry check
```

## KD-Tree Usage

The KD-Tree stores road bbox centroids and road node coordinates.

Used by:

- nearest road fallback candidate search
- nearest road node lookup for routing start/end points

KNN flow:

```text
GPS point -> KD-Tree nearest centroids -> road candidates -> exact point-to-polyline distance
```

## Complexity

| Query | Brute force | Indexed flow |
| --- | ---: | ---: |
| roads in bbox | O(n) bbox checks | O(log n + k) candidate traversal |
| nearby roads | O(n * segment_count) distance checks | O(log n + k) prefilter + exact distance on candidates |

Run the new comparison suite:

```bash
python -m benchmarks.spatial_index_benchmark
```

The `/benchmarks/spatial-index` API reports build time, candidate count, p50, p95, and p99 latency for each implementation.
| route start node | O(node_count) distance checks | O(log node_count) nearest lookup |

The implementation is intentionally static and small. For production-scale GIS data, a disk-backed index, PostGIS, or tiled spatial partitioning would be more appropriate.
