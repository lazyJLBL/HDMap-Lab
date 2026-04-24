# v1.0.0 Release Notes Draft

## Highlights

- Spatial data models for Point, Polyline, Polygon, RoadNode, RoadEdge, Trajectory, GeoFence, and POI
- GeoJSON and OSM XML loading
- SQLite runtime store with in-memory R-Tree / KD-Tree indexes
- Spatial query APIs for nearby roads, bbox roads, polygon roads, and polygon point statistics
- Geofence enter/exit detection
- Map Matching algorithms: nearest, candidate_cost, HMM/Viterbi
- Route planning with Dijkstra and A*, shortest distance, shortest time, avoid polygons, and waypoints
- React + Leaflet visualizer with fixed demo scenarios
- Docker Compose deployment
- Tests, benchmarks, CI workflow, algorithm docs, and interview notes

## Suggested GitHub Release Command

Run this after committing and pushing the v1.0.0-ready code:

```bash
gh release create v1.0.0 --title "HDMap-Lab v1.0.0" --notes-file docs/release_notes_v1.0.0.md
```

