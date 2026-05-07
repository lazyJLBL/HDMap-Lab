# Routing v2

HDMap-Lab routing is an explainable road-network experiment system. It keeps the original Dijkstra and A* entry points, and adds a v2 `/routing/explain` endpoint that reports why a path was selected.

## RoadGraph v2

`RoadGraph.build(nodes, roads)` converts `RoadEdge` objects into directed `GraphArc` records.

Each arc carries:

- `edge_id`, `from_node`, `to_node`
- `length_m`, `travel_time_s`, `speed_kph`
- `road_class`, `oneway`, `direction`
- `layer`, `bridge`, `tunnel`
- `turn_restrictions`
- original metadata

Non-oneway roads are inserted in both directions. Oneway roads only create the forward arc, so reverse routing is impossible unless the data includes a legal reverse edge.

## Cost Model

The v2 explainer supports three cost modes:

| Mode | Cost |
| --- | --- |
| `distance` | `length_m + turn_penalty_s * 8.33 + road_class_penalty + avoid_penalty` |
| `time` | `travel_time_s + turn_penalty_s + road_class_penalty / speed_kph` |
| `custom` | weighted sum of distance, travel time, turn penalty, avoid penalty, and road-class preference |

Road-class controls:

- `prefer_road_classes`: penalizes roads outside the preferred set.
- `avoid_road_classes`: strongly penalizes matching road classes.
- `speed_profile`: overrides class speed in time-mode experiments.

All cost components are returned in:

```json
{
  "distance": 0,
  "travel_time": 0,
  "turn_penalty": 0,
  "avoid_penalty": 0,
  "road_class_preference": 0
}
```

## Turn Cost

`app/routing/turn_cost.py` exposes:

- `compute_turn_angle(prev_edge, curr_edge)`
- `classify_turn(angle)`
- `turn_penalty_seconds(prev_edge, curr_edge)`
- `restricted_turn(prev_edge, curr_edge)`

Turn classes are:

`straight`, `slight_left`, `left`, `sharp_left`, `u_turn`, `slight_right`, `right`, `sharp_right`.

Turn restrictions are checked from edge metadata such as:

```json
{"from_edge": "edge_a", "to_edge": "edge_b", "type": "no_turn"}
```

## Avoid Polygon

Avoid polygons use the geometry kernel through `edges_intersecting_polygons`. Two modes are supported:

- hard avoid: intersecting edges are excluded before graph search.
- soft avoid: intersecting edges remain legal but receive a high penalty.

Debug layers include the route, route roads, and avoided edges as GeoJSON FeatureCollections.

## Dijkstra and A*

Dijkstra is used when `algorithm="dijkstra"` or when a custom heuristic is not admissible. A* uses:

- straight-line haversine distance for distance mode;
- straight-line time under the graph's maximum speed for time mode;
- zero heuristic for custom mode fallback.

These heuristics are admissible because they never overestimate the remaining road-network cost under non-negative edge weights.

## API

`POST /routing/explain`

```json
{
  "start": [116.390, 39.900],
  "end": [116.410, 39.920],
  "algorithm": "astar",
  "cost_mode": "distance",
  "turn_cost": true,
  "avoid_polygons": [],
  "prefer_road_classes": ["primary", "secondary"],
  "avoid_road_classes": ["service"],
  "return_debug_layers": true
}
```

Response shape:

```json
{
  "path": ["edge_a", "edge_b"],
  "total_distance_m": 0,
  "total_time_s": 0,
  "edge_count": 2,
  "turn_count": 1,
  "cost_breakdown": {},
  "steps": [
    {
      "road_id": "edge_a",
      "instruction": "go straight",
      "distance_m": 0,
      "road_class": "primary",
      "cost": 0
    }
  ],
  "debug_layers": {}
}
```

## Benchmark

```bash
python -m benchmarks.routing_benchmark --iterations 30 --output docs/assets/routing_benchmark.json
```

The benchmark compares:

- Dijkstra distance
- A* distance
- Dijkstra time
- A* time
- A* with turn cost
- A* with avoid polygon

Metrics include latency, visited nodes, path length, path time, and turn count.

## Complexity

Let `V` be node count, `E` edge count, and `S` state count where a state is `(node, previous_edge)`.

- Dijkstra: `O((S + E) log S)`
- A*: same worst case, often fewer visited nodes when the heuristic is informative
- avoid polygon prefilter: `O(R * P)` with `R` roads and `P` polygon edges in this pure-Python implementation
- turn-aware routing: increases state space because the previous edge affects legal turns and cost

## Current Limits

- Turn restrictions are simplified metadata rules, not a full OSM restriction relation parser.
- Avoid polygon checks are pure Python and intended for small experiments.
- Traffic signals, live congestion, lane-level routing, and time-dependent speeds are not modeled here.
- The heuristic assumes non-negative edge and penalty costs.
