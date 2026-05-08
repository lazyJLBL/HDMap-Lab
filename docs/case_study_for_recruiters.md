# Case Study for Recruiters

## Project Motivation

I built HDMap-Lab to turn ACM computational geometry training into inspectable map algorithm engineering. Instead of only solving contest problems, the project exposes robust predicates, dirty road-network repair, spatial indexing, HMM map matching, routing, trajectory analysis, APIs, tests, benchmarks, and a React/Leaflet workbench.

This is not a production HD map system. It is an algorithm workbench designed to show how geometry and graph algorithms become debuggable engineering components.

## Problem 1: Dirty Road Topology Repair

Real road extracts often contain duplicate edges, near-miss endpoints, illegal intersections, dangling edges, and overlapping segments. HDMap-Lab detects and repairs a first version of these cases:

- illegal intersection: crossing roads that should be split into graph nodes;
- dangling edge: short dead-end artifacts that can break routing and matching;
- duplicate edge: repeated geometry or reversed duplicate segments;
- near-miss snapping: endpoints that should connect but are separated by small GPS/import error.

The core skill demonstrated here is robust segment classification: cross, touch, endpoint touch, overlap, and disjoint.

## Problem 2: Spatial Index Benchmark

Map matching and routing need fast candidate generation. The project implements one interface over brute force, grid, quadtree, KD-tree, R-tree, STR R-tree, and Morton index experiments.

Brute force is kept as the correctness oracle. Each benchmark reports bbox query latency, candidate counts, recall, false positives, and p50/p95/p99 tail latency. This shows both algorithm design and engineering discipline: fast results are not accepted unless they match brute force.

## Problem 3: HMM Map Matching

Nearest-road matching fails when GPS drift puts points closer to a parallel service road, when sampling is sparse, or when a bridge crosses a surface road in 2D. HDMap-Lab implements HMM/Viterbi map matching to use sequence context.

The HMM cost model combines emission distance, graph transition distance, heading, turn penalty, road class prior, one-way compatibility, layer consistency, and optional speed feasibility. The API exposes these weights so a reviewer can see how changing the model changes cost or path selection.

## Problem 4: Explainable Routing

The routing module includes Dijkstra and A*, plus constraints that matter in map products:

- turn cost;
- avoid polygon;
- road-class preference;
- distance/time/custom cost modes;
- route metrics and debug layers.

The goal is not just to output a path, but to explain why that path was chosen.

## What I Learned

- Algorithms: robust predicates, segment intersection, point-in-polygon, HMM/Viterbi, graph shortest path, spatial indexes.
- Engineering: consistent data models, FastAPI contracts, debug GeoJSON layers, testable APIs.
- Testing: degenerate geometry cases, topology repair fixtures, map matching stress cases, spatial index recall checks.
- Benchmarking: brute-force baselines, p50/p95/p99 latency, candidate counts, correctness reporting.
- Visualization: React/Leaflet layers make algorithm decisions visible to non-specialists.

## How to Run

Backend:

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Benchmarks:

```bash
python -m benchmarks.spatial_index_benchmark
python -m benchmarks.map_matching_benchmark
python -m benchmarks.topology_repair_benchmark
```

Docker:

```bash
docker compose up --build
```

## Interview Talking Points

1. Why not use Shapely directly?
   The point of the project is to expose the geometry predicates and edge cases. Shapely/PostGIS are good production baselines, but they would hide the algorithmic decisions I want to demonstrate.

2. What is the hardest geometry bug?
   Near-collinear and endpoint-touch cases. A fixed epsilon can misclassify them, so the kernel uses translated determinants, scale-aware tolerance, and a Decimal fallback for ambiguous orientation.

3. How do you know an index is correct?
   Every index result is compared against brute force. The benchmark reports recall and false-positive rate, not only latency.

4. Why does nearest map matching fail?
   It optimizes each GPS point independently. Drift, sparse sampling, bridges, and one-way roads require sequence and graph context.

5. What does HMM add?
   It chooses the globally best candidate sequence using emission, transition, heading, turn, road class, one-way, layer, and speed costs.

6. How are HMM parameters tested?
   Tests verify that changing heading and road-class weights changes the reported matching cost, so API parameters are not dead fields.

7. What is implemented vs prototype?
   Geometry, topology repair v1, spatial benchmark, HMM matching, routing, trajectory analysis, FastAPI, and React are implemented. OpenDRIVE/Lanelet2 and PostGIS comparison are prototypes.

8. What would you do next with real data?
   Run larger OSM extracts, store benchmark reports with hardware and query distributions, and add more screenshots/GIFs for topology repair and matching cases.

9. What is the main engineering tradeoff?
   The project favors inspectability and tests over production-scale optimization. Some algorithms are intentionally explicit so interviewers can read and discuss them.

10. How would this become production-grade?
    Replace or validate core geometry with GEOS/PostGIS where required, add persistent storage, transition caching, larger datasets, observability, more map formats, and stronger data-quality pipelines.
