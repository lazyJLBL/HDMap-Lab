# API Reference

Base URL: `http://localhost:8000`

Coordinates use GeoJSON order: `[lon, lat]`.

## Dataset

`POST /datasets/load`

```json
{"source": "sample"}
```

Supported sources: `sample`, `geojson`, `osm_file`, `osm_online`.

`POST /datasets/reset` reloads sample data.

`GET /datasets/current` returns loaded dataset counts and ids.

## Roads

`GET /roads/nearby?lon=116.4015&lat=39.9110&k=5`

Returns nearest road candidates with projection point and distance.

## Spatial Query

`POST /spatial/query`

Supported `query_type` values:

- `roads_in_bbox`
- `points_in_polygon`
- `roads_in_polygon`

## Geofence

`POST /geofence/check`

Empty body uses the sample trajectory and sample geofences:

```json
{}
```

Returns enter/exit events.

## Map Matching

`POST /mapmatch`

```json
{
  "algorithm": "hmm",
  "k": 5,
  "sigma": 20,
  "beta": 50
}
```

Algorithms: `nearest`, `candidate_cost`, `hmm`.

## Routing

`POST /route/shortest`

```json
{
  "start": [116.390, 39.900],
  "end": [116.410, 39.920],
  "algorithm": "astar",
  "mode": "shortest_distance"
}
```

Supports `avoid_polygons` and `waypoints`.

## Visualization

- `GET /visualization/state`
- `GET /visualization/export`

These return GeoJSON layer bundles for the React + Leaflet visualizer.

