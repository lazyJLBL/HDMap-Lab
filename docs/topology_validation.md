# Topology Validation v2

`app/topology/validation.py` is the road-network quality inspection layer used before and after repair. It returns human-readable issues, aggregate metrics, a heuristic quality score, and GeoJSON debug layers that can be rendered by the frontend.

## API

```text
POST /topology/validate
```

Request:

```json
{
  "detect_crossings": true,
  "detect_overlaps": true,
  "detect_near_miss": false,
  "near_miss_tolerance_m": 1.0,
  "respect_layers": true,
  "return_debug_layers": true
}
```

Response shape:

```json
{
  "status": "ok",
  "data": {
    "summary": {},
    "issues": [],
    "metrics": {},
    "debug_layers": {},
    "quality_score": 0
  },
  "metrics": {},
  "warnings": [],
  "debug_layers": {}
}
```

## Issue Model

Every issue contains:

- `id`;
- `type`;
- `severity`: `info`, `warning`, `error`, or `critical`;
- `message`;
- `road_ids`;
- `node_ids`;
- `coordinate`;
- `suggested_fix`;
- `debug_geojson`.

The legacy fields `location`, `illegal_crossings`, `self_intersections`, `duplicate_edges`, and `dangling_edges` are preserved for existing callers.

## Checks

### Basic Statistics

- `node_count`;
- `edge_count`;
- `total_length_m`;
- `avg_edge_length_m`;
- `road_class_distribution`;
- `speed_distribution`;
- `oneway_ratio`.

### Connectivity

- weakly connected components;
- strongly connected components for directed/one-way flow;
- largest component ratio;
- isolated nodes;
- unreachable components;
- dead-end nodes;
- degree distribution;
- suspicious high-degree nodes.

### Geometry Errors

- `self_intersecting_road`;
- `duplicated_points_in_road`;
- `zero_length_segment`;
- `overlapping_roads`;
- `crossing_without_node`;
- `near_miss_intersection`;
- `sharp_angle_node`.

### Topology Errors

- `dangling_edge`;
- `duplicate_edge`;
- `reverse_duplicate_edge`;
- `one_way_dead_end`.

### Semantic Errors

- `invalid_speed`;
- `missing_road_class`;
- `missing_geometry`;
- `invalid_layer`;
- `inconsistent_bridge_tunnel_layer`;
- `oneway_metadata_conflict`.

## Layer Handling

When `respect_layers=true`, crossing and overlap checks ignore roads with different `(layer, bridge, tunnel)` metadata. This prevents a bridge or tunnel from being flagged as an illegal planar crossing. The validator does not infer missing layer metadata; if the input does not say a crossing is grade separated, it is treated as planar.

## Quality Score

`quality_score` is a simple heuristic, not a formal map-quality guarantee:

| Severity | Penalty |
| --- | ---: |
| critical | 10 |
| error | 5 |
| warning | 2 |
| info | 0.5 |

The score starts at 100 and is clamped to 0. The intent is to make before/after repair comparisons easy to scan.

## Debug Layers

`debug_layers` is a dictionary of GeoJSON `FeatureCollection`s keyed by issue type, for example:

```json
{
  "crossing_without_node": {
    "type": "FeatureCollection",
    "features": [
      {"type": "Feature", "properties": {"layer": "crossing_without_node", "severity": "error"}, "geometry": {}}
    ]
  }
}
```

Each layer includes issue coordinates and the involved road geometries when available.

## Complexity

Let `N` be node count, `R` road count, and `S` total road segments.

| Check | Complexity |
| --- | --- |
| Basic stats | `O(N + R)` |
| Weak connectivity | `O(N + R)` |
| Strong connectivity | `O(N + R)` |
| Duplicate edge detection | `O(R * P)` where `P` is average points per road |
| Internal self-intersection | Worst `O(P^2)` per road |
| Road crossing/overlap detection | Worst `O(S^2)` |
| Near-miss scan | Worst `O(S^2)` |

The v2 validator is intentionally transparent. City-scale runs should combine these checks with a spatial-index broad phase to avoid quadratic scans.

## Example

```python
from app.topology.validation import validate_topology

report = validate_topology(
    nodes,
    roads,
    detect_crossings=True,
    detect_overlaps=True,
    detect_near_miss=True,
    near_miss_tolerance_m=1.0,
    respect_layers=True,
)

print(report.quality_score)
for issue in report.issues:
    print(issue.id, issue.type, issue.severity, issue.suggested_fix)
```

## Current Limits

- The validator is not a legal road-rule engine.
- It does not infer bridges/tunnels when metadata is missing.
- Near-miss detection is geometric and can flag intentional close parallel roads.
- Crossing and overlap scans are brute force until integrated with spatial index v2.
