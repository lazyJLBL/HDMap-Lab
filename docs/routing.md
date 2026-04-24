# Routing

HDMap-Lab builds a graph from `RoadNode` and `RoadEdge`.

## Graph Model

- `RoadNode`: graph vertex with `id`, `lon`, `lat`
- `RoadEdge`: graph edge with `from_node`, `to_node`, geometry, length, speed limit, oneway flag
- non-oneway roads are inserted in both directions

## Weight Modes

`shortest_distance`:

```text
weight = RoadEdge.length
```

`shortest_time`:

```text
weight = RoadEdge.length / speed_limit
```

## Dijkstra

Dijkstra expands the lowest-known-cost node until the destination is reached. It guarantees the shortest path when all edge weights are non-negative.

## A*

A* adds a heuristic to prioritize nodes closer to the target:

```text
priority = actual_cost_from_start + heuristic_to_goal
```

HDMap-Lab uses haversine distance as the heuristic for `shortest_distance`, and estimated travel time under a high reference speed for `shortest_time`.

## Avoid Polygon

Avoid polygons are applied by temporarily excluding road edges that intersect restricted polygons:

```text
avoid polygon -> roads intersecting polygon -> excluded edge ids -> graph search
```

The base graph remains unchanged.

## Waypoints

Waypoints are handled by splitting the route:

```text
start -> waypoint_1 -> waypoint_2 -> end
```

Each segment is planned independently and then merged into one route geometry and road sequence.

