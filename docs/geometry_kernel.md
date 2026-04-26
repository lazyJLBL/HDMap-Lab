# Geometry Kernel

`app/geometry_kernel/` contains the self-developed computational geometry core used by topology repair, geofencing, routing constraints, and map matching.

Implemented algorithms:

- robust orientation with scaled epsilon
- segment intersection with `none`, `point`, and `overlap` results
- point-in-polygon with holes and boundary classification
- point-to-segment and point-to-polyline projection
- polyline length and Ramer-Douglas-Peucker simplification
- polygon area, centroid, bbox, and convex hull
- conservative road corridor bbox buffer

Degenerate cases covered by tests:

- collinear points
- overlapping segments
- endpoint intersection
- polygon holes
- boundary points
- nearly straight polyline simplification

The kernel intentionally avoids Shapely, GEOS, rtree, GeoPandas, and PostGIS in core paths so the implementation demonstrates the underlying geometry.
