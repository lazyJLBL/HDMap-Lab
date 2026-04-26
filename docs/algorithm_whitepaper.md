# HDMap-Lab Algorithm Whitepaper

## Problem Definition

HDMap-Lab targets the algorithmic parts of map engineering: robust geometry predicates, dirty road-network topology repair, spatial index tradeoffs, GPS-to-road map matching, trajectory similarity, and explainable route planning.

## Core Design

- Geometry is implemented in `geometry_kernel` using scaled epsilon predicates and explicit degenerate-case handling.
- Road topology is modeled as nodes, directed graph arcs, and road metadata including class, speed, direction, lane count, and turn restrictions.
- Spatial indexes share a common query contract so brute force, grid, quadtree, R-tree, and STR R-tree can be benchmarked under the same workload.
- HMM map matching uses distance emission plus transition path cost, heading consistency, turn penalty, one-way handling, and road-class prior.
- Routing supports avoid polygons and an explainable cost breakdown for distance, travel time, turn cost, and road-class preference.

## Complexity

- Segment intersection: `O(1)` per segment pair.
- Point-in-polygon: `O(n)` for ring edges.
- Topology illegal crossing detection: `O(E^2 * S^2)` in v1; spatial-index pruning is the planned scale-up path.
- Grid query: expected `O(c + k)` where `c` is touched cells and `k` is candidates.
- R-tree/STR R-tree query: expected `O(log n + k)` for well-packed data.
- HMM/Viterbi: `O(T * K^2 * P)` where `T` is GPS points, `K` candidates per point, and `P` shortest-path transition cost.

## Failure Modes

- v1 corridor buffer is conservative and bbox-based, not a full offset curve implementation.
- Topology splitting currently handles point intersections and duplicate endpoint edges; full collinear merge is tracked as a future refinement.
- HMM overpass accuracy still depends on missing elevation/lane metadata.
- OpenDRIVE support is a stub for lane model exchange, not a full parser.

## Benchmarks

Use:

```bash
python -m benchmarks.spatial_index_benchmark
python -m benchmarks.map_matching_benchmark
python -m benchmarks.topology_repair_benchmark
python -m benchmarks.city_scale_benchmark --roads data/roads.geojson --queries 20
```

The benchmark focus is not only average speed, but p95/p99 latency, candidate count, and failure-case analysis.

PostGIS comparison is kept outside the core algorithm path:

```bash
docker compose up -d postgis
python -m benchmarks.postgis_benchmark --roads data/roads.geojson
```
