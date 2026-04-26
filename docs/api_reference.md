# API Reference

Base URL: `http://localhost:8000`

All coordinates use GeoJSON order: `[lon, lat]`. Distances are meters and times are seconds.

## Health And Stats

### GET /health

Request: no body.

Response:

```json
{
  "status": "ok",
  "roads": 13,
  "nodes": 9,
  "trajectories": 1
}
```

### GET /stats

Request: no body.

Response:

```json
{
  "dataset": {
    "roads": 13,
    "nodes": 9,
    "trajectories": 1,
    "geofences": 1,
    "pois": 3
  },
  "indexes": {
    "road_rtree": "ready",
    "road_kdtree": "ready",
    "road_graph": {
      "nodes": 9,
      "edges": 26
    }
  }
}
```

## Dataset APIs

### POST /datasets/load

Load sample data, GeoJSON files or payloads, offline OSM XML, or online OSM data.

Request:

```json
{
  "source": "sample"
}
```

GeoJSON file request:

```json
{
  "source": "geojson",
  "roads_path": "data/roads.geojson",
  "trajectories_path": "data/trajectories.geojson",
  "geofences_path": "data/geofences.geojson",
  "pois_path": "data/pois.geojson"
}
```

OSM file request:

```json
{
  "source": "osm_file",
  "osm_path": "data/sample.osm"
}
```

Online OSM bbox request:

```json
{
  "source": "osm_online",
  "bbox": [116.390, 39.900, 116.410, 39.920]
}
```

Response:

```json
{
  "status": "loaded",
  "source": "sample",
  "counts": {
    "nodes": 9,
    "roads": 13,
    "trajectories": 1,
    "geofences": 1,
    "pois": 3
  }
}
```

Fields:

- `source`: `sample`, `geojson`, `osm_file`, or `osm_online`
- `bbox`: `[min_lon, min_lat, max_lon, max_lat]`
- `place`: optional place name for online OSM lookup

### POST /datasets/reset

Reload the built-in sample dataset.

Request: no body.

Response:

```json
{
  "status": "reset",
  "source": "sample",
  "counts": {
    "nodes": 9,
    "roads": 13,
    "trajectories": 1,
    "geofences": 1,
    "pois": 3
  }
}
```

### GET /datasets/current

Request: no body.

Response:

```json
{
  "roads": 13,
  "nodes": 9,
  "trajectories": ["traj_001"],
  "geofences": ["fence_campus"],
  "pois": ["poi_gate", "poi_station", "poi_parking"],
  "bounds": [116.39, 39.9, 116.41, 39.92]
}
```

## Road APIs

### GET /roads/nearby

Query the nearest roads around a GPS point.

Request:

```text
GET /roads/nearby?lon=116.4015&lat=39.9110&k=5
```

Response:

```json
{
  "roads": [
    {
      "road_id": "edge_h_11_21",
      "distance": 96.31,
      "projection_point": [116.4015, 39.91],
      "road_heading": 89.99,
      "geometry": {
        "type": "LineString",
        "coordinates": [[116.4, 39.91], [116.41, 39.91]]
      }
    }
  ]
}
```

Fields:

- `lon`, `lat`: query point
- `k`: number of candidate roads, default `5`
- `projection_point`: closest point on the matched road geometry

## Spatial Query APIs

### POST /spatial/query

Supported query types:

- `roads_in_bbox`
- `points_in_polygon`
- `roads_in_polygon`

Roads in bbox request:

```json
{
  "query_type": "roads_in_bbox",
  "bbox": [116.399, 39.909, 116.411, 39.911]
}
```

Response:

```json
{
  "query_type": "roads_in_bbox",
  "count": 3,
  "roads": ["edge_h_11_21", "edge_v_10_11", "edge_v_20_21"]
}
```

Points in polygon request:

```json
{
  "query_type": "points_in_polygon",
  "target": "trajectory_points",
  "polygon": [
    [
      [116.398, 39.908],
      [116.406, 39.908],
      [116.406, 39.916],
      [116.398, 39.916],
      [116.398, 39.908]
    ]
  ]
}
```

Response:

```json
{
  "query_type": "points_in_polygon",
  "count": 2,
  "points": [
    {
      "id": "traj_001_1",
      "trajectory_id": "traj_001",
      "point_index": 1,
      "lon": 116.3975,
      "lat": 39.9101,
      "timestamp": "2026-01-01T10:00:10"
    }
  ]
}
```

Fields:

- `bbox`: `[min_lon, min_lat, max_lon, max_lat]`
- `polygon`: GeoJSON Polygon coordinates without the outer geometry object
- `target`: `trajectory_points` or `pois`

## Geofence APIs

### POST /geofence/check

Empty request uses the loaded sample trajectory and geofences.

Request:

```json
{}
```

Custom request:

```json
{
  "trajectory": {
    "id": "traj_custom",
    "points": [
      {"lon": 116.3975, "lat": 39.9101, "timestamp": "2026-01-01T10:00:10"},
      {"lon": 116.4020, "lat": 39.9102, "timestamp": "2026-01-01T10:00:20"}
    ]
  },
  "geofences": [
    {
      "id": "fence_custom",
      "name": "Custom Zone",
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [116.398, 39.908],
            [116.406, 39.908],
            [116.406, 39.916],
            [116.398, 39.916],
            [116.398, 39.908]
          ]
        ]
      }
    }
  ]
}
```

Response:

```json
{
  "trajectory_id": "traj_001",
  "entered": true,
  "events": [
    {
      "fence_id": "fence_campus",
      "fence_name": "Campus Delivery Zone",
      "point_index": 2,
      "timestamp": "2026-01-01T10:00:20",
      "event": "enter",
      "point": [116.402, 39.9102]
    }
  ]
}
```

Fields:

- `event`: `enter` or `exit`
- `point_index`: index of the trajectory point where the state changed

## Map Matching APIs

### POST /mapmatch

Request:

```json
{
  "algorithm": "hmm",
  "k": 5,
  "sigma": 20,
  "beta": 50
}
```

Custom trajectory request:

```json
{
  "algorithm": "candidate_cost",
  "k": 5,
  "trajectory": {
    "id": "traj_custom",
    "points": [
      {"lon": 116.3910, "lat": 39.9098},
      {"lon": 116.3975, "lat": 39.9101}
    ]
  }
}
```

Response:

```json
{
  "trajectory_id": "traj_001",
  "algorithm": "hmm",
  "matched_road_sequence": ["edge_h_01_11", "edge_h_11_21"],
  "confidence": 0.86,
  "matches": [
    {
      "point_index": 0,
      "candidate_count": 5,
      "matched_road_id": "edge_h_01_11",
      "distance": 12.4,
      "projection_point": [116.391, 39.91],
      "emission_prob": 0.82
    }
  ]
}
```

Fields:

- `algorithm`: `nearest`, `candidate_cost`, or `hmm`
- `k`: number of candidate roads retained per GPS point
- `sigma`: HMM emission distance parameter in meters
- `beta`: HMM transition distance parameter in meters
- `confidence`: demo-scale confidence score derived from matching distance

## Routing APIs

### POST /route/shortest

Request:

```json
{
  "start": [116.390, 39.900],
  "end": [116.410, 39.920],
  "algorithm": "astar",
  "mode": "shortest_distance"
}
```

Avoid polygon and waypoint request:

```json
{
  "start": [116.390, 39.900],
  "waypoints": [[116.400, 39.910]],
  "end": [116.410, 39.920],
  "algorithm": "dijkstra",
  "mode": "shortest_time",
  "avoid_polygons": [
    [
      [
        [116.398, 39.908],
        [116.406, 39.908],
        [116.406, 39.916],
        [116.398, 39.916],
        [116.398, 39.908]
      ]
    ]
  ]
}
```

Response:

```json
{
  "route_id": "route_001",
  "algorithm": "astar",
  "mode": "shortest_distance",
  "distance": 3366.19,
  "estimated_time": 291.44,
  "road_sequence": ["edge_diag_00_11", "edge_h_11_21", "edge_v_21_22"],
  "geometry": {
    "type": "LineString",
    "coordinates": [[116.39, 39.9], [116.4, 39.91], [116.41, 39.91], [116.41, 39.92]]
  },
  "excluded_edges": []
}
```

Fields:

- `algorithm`: `dijkstra` or `astar`
- `mode`: `shortest_distance` or `shortest_time`
- `avoid_polygons`: road edges intersecting these polygons are excluded for this request
- `waypoints`: route is split into ordered segments and then merged

## Visualization APIs

### GET /visualization/state

Request: no body.

Response:

```json
{
  "roads": {"type": "FeatureCollection", "features": []},
  "trajectories": {"type": "FeatureCollection", "features": []},
  "geofences": {"type": "FeatureCollection", "features": []},
  "pois": {"type": "FeatureCollection", "features": []},
  "bounds": [116.39, 39.9, 116.41, 39.92]
}
```

## Experiment APIs

New algorithm-lab endpoints return a uniform envelope:

```json
{
  "status": "ok",
  "data": {},
  "metrics": {},
  "warnings": [],
  "debug_layers": {}
}
```

### POST /topology/validate

Validates the loaded road graph and reports connected components, dangling edges, duplicate edges, illegal crossings, overlapping roads, and self-intersections.

### POST /topology/repair

Request:

```json
{
  "snap_tolerance_m": 1.0,
  "apply": false
}
```

Returns `fixed_roads` GeoJSON, before/after topology reports, and operation counts.

### POST /benchmarks/spatial-index

Request:

```json
{
  "iterations": 50
}
```

Compares brute force, grid, quadtree, R-tree, and STR R-tree with build time, candidate count, p50, p95, and p99 latency.

### POST /benchmarks/map-matching

Runs synthetic GPS stress cases and compares nearest matching with HMM using precision, recall, confidence, and latency.

### POST /trajectory/analyze

Analyzes a loaded or custom trajectory with Frechet, Hausdorff, DTW, simplification, outlier detection, and route-deviation metrics.

### POST /routing/explain

Runs turn-cost aware routing and returns route steps plus a cost breakdown for distance, travel time, turn cost, road-class preference, and excluded edges.

### GET /visualization/export

Request: no body.

Response:

```json
{
  "exported_at": "2026-04-24T00:00:00+00:00",
  "format": "geojson-layer-bundle",
  "layers": {
    "roads": {"type": "FeatureCollection", "features": []},
    "trajectories": {"type": "FeatureCollection", "features": []},
    "geofences": {"type": "FeatureCollection", "features": []},
    "pois": {"type": "FeatureCollection", "features": []},
    "bounds": [116.39, 39.9, 116.41, 39.92]
  }
}
```
