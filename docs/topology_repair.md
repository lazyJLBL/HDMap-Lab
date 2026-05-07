# Topology Repair v2

`app/topology/repair.py` turns a dirty road-edge list into repaired roads, rebuilt endpoint nodes, a before/after topology report, operation logs, and GeoJSON `debug_layers`.

The implementation is still a lab-scale pure-Python repair pipeline, not a production conflation engine. The goal is to make every repair decision explicit and testable.

## Pipeline

1. **Validate before repair**
   - Input: `RoadNode`, `RoadEdge`.
   - Output: existing `TopologyReport` from `validate_topology`.

2. **Snap close nodes v2**
   - Uses union-find to cluster endpoint nodes within `snap_tolerance_m`.
   - Representative can be the cluster centroid or the first node.
   - Does not snap the two endpoints of the same road, which avoids collapsing short edges.
   - When `respect_layers=true`, nodes are snapped only if their `(layer, bridge, tunnel)` context is compatible.
   - Output fields:
     - `snapped_pairs`;
     - `clusters`;
     - `moved_distance_stats`.

3. **Split roads at intersections v2**
   - Scans road segment pairs and uses the geometry kernel's `segment_intersection`.
   - Splits only true planar interior intersections.
   - Skips endpoint touches, overpasses with different layer/bridge/tunnel metadata, and roads with `metadata.allow_crossing=true`.
   - Supports multiple split points on the same segment sorted by segment parameter `t`.
   - Output: `split_events`.

4. **Remove duplicate edges v2**
   - Detects same-direction and reverse-direction duplicate geometries.
   - Keeps the road with richer metadata.
   - Does not remove a legal pair of opposite one-way roads digitized in reverse directions.
   - Output: `duplicate_groups`.

5. **Merge collinear roads**
   - Optional through `merge_collinear=true`.
   - Merges roads when:
     - they meet at an endpoint;
     - road class, speed, oneway, direction, and layer are compatible;
     - the middle node has degree 2;
     - the turn angle is below the threshold.
   - Output: `merged_events`.

6. **Handle dangling edges**
   - Modes:
     - `mark_only`;
     - `remove_short`;
     - `remove_all`.
   - `remove_short` uses `dangling_length_threshold_m`.
   - Output: `dangling_edges`.

7. **Validate after repair**
   - Rebuilds endpoint nodes from repaired geometry.
   - Returns `before`, `after`, `topology_report`, `operations`, and `debug_layers`.

## API

```text
POST /topology/repair
```

Request fields:

```json
{
  "snap_tolerance_m": 1.0,
  "apply": false,
  "split_intersections": true,
  "merge_collinear": false,
  "dangling_mode": "mark_only",
  "dangling_length_threshold_m": 10.0,
  "respect_layers": true,
  "preserve_metadata": true,
  "return_debug_layers": true
}
```

Response includes:

- `data.operations`;
- `data.before`;
- `data.after`;
- `data.fixed_roads`;
- `data.topology_report`;
- `debug_layers`.

## CLI

```bash
python -m scripts.repair_topology \
  --input data/roads.geojson \
  --output datasets/synthetic/fixed_roads.geojson \
  --report datasets/synthetic/topology_report.json \
  --snap-tolerance-m 1.0 \
  --merge-collinear \
  --dangling-mode mark_only
```

## Metadata Preservation

Repair keeps road metadata by default and adds:

- `source_edge`;
- `original_ids`;
- `repair_history`;
- duplicate removal notes where applicable;
- dangling markers when `dangling_mode=mark_only`.

Road-level fields such as `road_class`, `speed_limit`, `oneway`, `direction`, and `lane_count` remain on `RoadEdge`. Layering fields such as `layer`, `bridge`, and `tunnel` are read from `metadata`.

## Debug Layers

`repair_topology(..., return_debug_layers=True)` returns:

```json
{
  "original_roads": {"type": "FeatureCollection", "features": []},
  "snapped_nodes": {"type": "FeatureCollection", "features": []},
  "split_points": {"type": "FeatureCollection", "features": []},
  "duplicate_edges": {"type": "FeatureCollection", "features": []},
  "merged_roads": {"type": "FeatureCollection", "features": []},
  "dangling_edges": {"type": "FeatureCollection", "features": []},
  "repaired_roads": {"type": "FeatureCollection", "features": []}
}
```

These layers are designed to render directly in the React/Leaflet workbench.

## Why Layers Matter

A 2D segment crossing is not always a road-network node. Bridges, tunnels, and explicit layer metadata represent grade separation. Splitting those lines would create false turns and invalid routing transitions. For this reason, repair defaults to `respect_layers=true` and requires matching `(layer, bridge, tunnel)` metadata before snapping nodes or splitting crossings.

## Before/After Example

Input:

- road A: `(0,0) -> (2,0)`;
- road B: `(1,-1) -> (1,1)`;
- no shared node at `(1,0)`.

Repair:

- detects a `cross` segment intersection;
- inserts `(1,0)` into both roads;
- emits two `split_events`;
- returns four repaired road pieces;
- validation no longer reports the crossing as illegal.

## Complexity

Let `N` be nodes, `R` roads, `S` total segments, and `D` duplicate groups.

| Step | Complexity |
| --- | --- |
| Snap close nodes | `O(N^2)` pair scan plus near-constant union-find operations |
| Split intersections | `O(S^2)` segment-pair scan |
| Insert split points | `O(S + K log K)` where `K` is split events per segment |
| Duplicate detection | `O(R * P log P)` for geometry key normalization, `P` points per road |
| Merge collinear roads | Iterative local scan, worst `O(R^2)` |
| Dangling handling | `O(R)` |

The current implementation favors transparency over scale. Later spatial-index broad-phase filtering should reduce snap and split scans for city-scale data.

## Current Limits

- No full road conflation or lane-level topology inference.
- Split detection is segment-pair brute force.
- Layer semantics depend on available `metadata.layer`, `metadata.bridge`, and `metadata.tunnel`.
- Duplicate detection uses rounded coordinates and exact geometry shape, not Hausdorff-like similarity.
- Merge collinear roads handles simple degree-2 chains, not complex multi-edge junctions.
