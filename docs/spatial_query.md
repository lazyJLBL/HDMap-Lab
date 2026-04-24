# Spatial Query

Spatial query APIs provide basic GIS operations over roads, trajectories, and POIs.

## Nearby Roads

Endpoint:

```text
GET /roads/nearby?lon=116.4015&lat=39.9110&k=5
```

Flow:

```text
GPS point -> bbox radius search -> KD-Tree fallback -> exact point-to-polyline distance -> top K roads
```

Returned fields include road id, distance in meters, projection point, road heading, and road geometry.

## Roads In BBox

Endpoint:

```text
POST /spatial/query
```

Payload:

```json
{
  "query_type": "roads_in_bbox",
  "bbox": [116.399, 39.909, 116.411, 39.911]
}
```

The R-Tree returns all roads whose precomputed bbox intersects the query bbox.

## Points In Polygon

Targets:

- `trajectory_points`
- `pois`

The polygon bbox is used as a cheap prefilter when available, and point-in-polygon uses ray casting with boundary detection.

