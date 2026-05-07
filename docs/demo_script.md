# 3-Minute Demo Script

## 0:00 - 0:30: Project Background and Goal

Open with the main line:

HDMap-Lab is a computational-geometry based map algorithm workbench for dirty road-network repair, spatial index benchmarking, HMM map matching, trajectory analysis, and explainable routing.

中文讲法：这是我把 ACM 计算几何能力工程化到地图算法场景里的项目，目标不是做一个完整商业 GIS，而是用可运行的实验展示几何、拓扑、索引、匹配和路径规划能力。

Show the React + Leaflet workbench and point out the map layers, left-side experiment controls, and result panel.

## 0:30 - 1:15: Dirty Road Repair

Click `Load Sample`, then `Repair`.

Explain:

- The input is a dirty road-network case with duplicated edges, close endpoints, illegal crossings, dangling edges, and overlapping roads.
- The backend runs topology validation first, then snapping, intersection splitting, duplicate removal, optional dangling handling, and returns before/after summaries.
- The map can show original roads, repaired roads, split points, and issue/debug markers.

Interview hook:

The key geometry piece is segment classification: cross vs endpoint touch vs overlap vs collinear disjoint. This avoids treating every intersection as the same repair operation.

## 1:15 - 2:00: Spatial Index Benchmark

Click `Index Bench`.

Explain:

- The benchmark runs the same query set across brute force, grid, quadtree, R-tree, STR R-tree, KD-tree/Morton variants depending on the request.
- Brute force is the correctness baseline. I report recall and false-positive rate, not just latency.
- The result panel shows p95 latency and recall, while the map can display sample indexed roads and query bbox.

Interview hook:

The benchmark is intentionally local and reproducible. I do not claim city-scale performance unless a real OSM/GeoJSON extract and generated JSON/Markdown report are provided.

## 2:00 - 2:40: HMM Map Matching / Routing

Choose `HMM`, click `Match`, then run `Stress Test` or `Explain`.

Explain:

- nearest matching is a local baseline; HMM uses a candidate sequence and Viterbi-style dynamic programming.
- The cost includes emission distance, transition/network consistency, heading, road class, layer, and one-way compatibility.
- Routing uses Dijkstra/A* and supports avoid polygons, turn cost, preferred road classes, and explanation steps.

Interview hook:

Parallel-road drift is the clearest case: nearest may jump to a physically close service road, while HMM can prefer a globally consistent road sequence.

## 2:40 - 3:00: Summary

Close with:

This project demonstrates the path from algorithmic geometry to engineering: robust predicates, topology repair, benchmark correctness, map matching evaluation, routing explanation, API design, frontend visualization, tests, and honest documentation.

Emphasize scope:

It is an algorithm workbench/prototype. OpenDRIVE/Lanelet2 and city-scale benchmarking are prototype/generator features unless backed by local data and generated reports.
