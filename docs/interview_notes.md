# Interview Notes

## Why use R-Tree?

Road edges are spatial rectangles after bbox preprocessing. R-Tree supports efficient rectangle intersection queries, which fits roads-in-bbox and candidate prefiltering.

## KD-Tree vs R-Tree

KD-Tree indexes points and is useful for nearest node or centroid lookup. R-Tree indexes rectangles and is better for road bbox intersection.

## How does point-in-polygon work?

HDMap-Lab uses ray casting. A horizontal ray from the point counts polygon edge crossings. Odd crossings mean inside, even crossings mean outside. Boundary is handled separately with point-to-segment distance.

## How is point-to-road distance computed?

Each road polyline is split into line segments. The GPS point is projected onto each segment, clamped to the segment endpoints, and the minimum projected distance is selected.

## Why not only nearest road for Map Matching?

Nearest road ignores trajectory direction and road connectivity. It can choose the wrong road around intersections, parallel roads, or overpasses.

## HMM emission and transition probabilities

Emission probability measures how likely a GPS point is observed from a candidate road, mainly based on distance. Transition probability measures whether adjacent candidate roads explain the GPS movement distance through the road graph.

## Dijkstra vs A*

Dijkstra expands by known cost only. A* adds a heuristic estimate to the target, so it often explores fewer nodes while preserving optimality when the heuristic is admissible.

## A* heuristic choice

For shortest distance, haversine distance is admissible because road distance cannot be shorter than straight-line distance. For shortest time, straight-line distance divided by a high reference speed is used.

## How avoid polygons work

Road edges intersecting avoid polygons are excluded from the search for the current request. The stored road graph is not permanently modified.

## How to scale to larger road networks

Partition the road network by tiles, use disk-backed spatial indexes, cache graph search results, store data in PostGIS or a graph database, and load only relevant regions into memory.

## How to handle GPS drift and parallel roads

Increase candidate count, use heading and speed constraints, add road class priors, tune HMM sigma/beta, and use multiple observations instead of making a per-point greedy decision.

