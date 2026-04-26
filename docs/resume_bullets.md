# Resume Bullets

## GIS Engineering Version

- Designed and implemented HDMap-Lab, a lightweight GIS spatial algorithm platform supporting GeoJSON / OSM road loading, spatial indexing, geofence detection, trajectory analysis, and map visualization.
- Built R-Tree / KD-Tree based spatial query modules for nearby road search, bbox road query, polygon point statistics, and road candidate retrieval.
- Implemented geometry primitives including point-in-polygon, point-to-polyline projection, bbox intersection, and polyline length calculation.

## Map Algorithm Version

- Implemented trajectory Map Matching with nearest-road matching, candidate-cost matching, and HMM/Viterbi global sequence optimization.
- Modeled road networks as RoadNode / RoadEdge graphs and implemented Dijkstra / A* routing with shortest distance, shortest time, avoid-polygon constraints, and waypoint routing.
- Built candidate search and cost models combining GPS-road distance, heading consistency, and road-network connectivity.
- Upgraded HDMap-Lab into a computational geometry lab with a self-developed robust geometry kernel, topology repair, multi-index spatial benchmarks, HMM stress tests, trajectory similarity metrics, and explainable routing APIs.

## Backend Platform Version

- Built a FastAPI-based spatial computation backend exposing road query, geofence, map matching, route planning, dataset loading, and visualization APIs.
- Used SQLite for runtime persistence and in-memory spatial indexes for low-latency algorithm execution.
- Added React + Leaflet visualization and Docker Compose deployment to make the spatial algorithm platform easy to demo and evaluate.
