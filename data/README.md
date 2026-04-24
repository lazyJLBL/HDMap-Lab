# Data

This directory contains the built-in HDMap-Lab demo dataset.

## Files

- `roads.geojson`: sample road network as GeoJSON LineString features
- `trajectories.geojson`: sample GPS trajectory as GeoJSON LineString
- `geofences.geojson`: sample polygon geofence
- `pois.geojson`: sample POIs
- `sample.osm`: tiny OSM XML file for loader tests

## Coordinate Order

All coordinates use GeoJSON order:

```text
[lon, lat]
```

Distance is returned in meters. Travel time is returned in seconds.

## Road Fields

Road features may include:

- `id`
- `from`
- `to`
- `road_type`
- `speed_limit`
- `oneway`
- `length`

If `length` is missing, HDMap-Lab computes it from the road geometry.

## OSM Attribution

Online OSM loading uses Nominatim and Overpass. Data from OpenStreetMap is available under the Open Database License. When using real OSM data, keep OpenStreetMap attribution in your application or documentation.

## Replacing With Your Own Data

Use GeoJSON:

```json
{
  "source": "geojson",
  "roads_path": "data/my_roads.geojson",
  "trajectories_path": "data/my_trajectories.geojson",
  "geofences_path": "data/my_geofences.geojson",
  "pois_path": "data/my_pois.geojson"
}
```

Use OSM XML:

```json
{
  "source": "osm_file",
  "osm_path": "data/my_area.osm"
}
```

Use online OSM bbox:

```json
{
  "source": "osm_online",
  "bbox": [116.390, 39.900, 116.410, 39.920]
}
```

After loading, verify the dataset:

```text
GET /datasets/current
GET /stats
GET /visualization/state
```

