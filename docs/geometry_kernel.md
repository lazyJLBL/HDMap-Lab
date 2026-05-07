# Robust Geometry Kernel v2

`app/geometry_kernel/` is HDMap-Lab's pure-Python computational geometry core. It is intentionally implemented without Shapely, GEOS, PostGIS, or GeoPandas in the core path so the project can expose the actual geometry predicates and degenerate-case handling used by topology repair, routing constraints, map matching, and trajectory analysis.

## Why Robust Predicates Matter

The orientation predicate

```text
orient(a, b, c) = (bx - ax)(cy - ay) - (by - ay)(cx - ax)
```

is the base test for collinearity, segment intersection, polygon boundary checks, and self-intersection detection. Floating-point arithmetic can make this determinant unstable when coordinates are large but local differences are small, or when the three points are nearly collinear. A fixed global epsilon is also unsafe: it can be too small for city-scale coordinates and too large for tiny geometry.

`predicates.py` therefore uses:

- translated determinants to reduce cancellation;
- scale-aware tolerances based on local coordinate deltas;
- a `Decimal` fallback in `robust_orientation` for ambiguous near-collinear triples;
- scale-aware point and bbox tolerances for endpoint and bbox tests.

This is not a full exact arithmetic kernel like GEOS, but it is much more reliable than a single `EPSILON` branch.

## Modules

### Predicates

Implemented in `app/geometry_kernel/predicates.py`:

- `orientation_value(a, b, c)`: signed twice-area determinant.
- `orientation(a, b, c, eps=None)`: clockwise / counter-clockwise / collinear classification.
- `robust_orientation(a, b, c)`: fallback path for ambiguous near-collinear triples.
- `signed_area_ring(points)`: signed ring area, positive for CCW.
- `is_collinear(a, b, c)`, `on_segment(point, start, end)`, `same_point(a, b)`.
- `bbox_of_points(points)`, `bbox_intersects(a, b)`, `bbox_contains_point(bbox, point)`.

Complexity: all predicate and bbox operations are `O(1)` except `signed_area_ring` and `bbox_of_points`, which are `O(n)`.

### Segment Intersection

Implemented in `app/geometry_kernel/intersection.py`.

`segment_intersection(a1, a2, b1, b2)` returns a `SegmentIntersection` dataclass:

```python
SegmentIntersection(
    kind="none" | "point" | "overlap",
    point=(x, y) | None,
    overlap=((x1, y1), (x2, y2)) | None,
    relation="cross" | "touch" | "overlap" | "disjoint" | "endpoint_touch" | "collinear_disjoint",
)
```

The classifier handles:

- proper crossing segments;
- endpoint touches;
- T-junction touches;
- complete and partial overlaps;
- reversed overlaps;
- parallel disjoint segments;
- collinear but separated segments;
- zero-length segment degeneracy.

Complexity: `O(1)` per segment pair. Topology repair and validation still need broad-phase spatial filtering for large road sets.

### Polygon

Implemented in `app/geometry_kernel/polygon.py`.

Supported operations:

- `point_in_ring`, `point_in_polygon`, `point_in_multipolygon`;
- boundary policy: `"boundary"`, `"inside"`, or `"outside"`;
- polygons with holes;
- `polygon_area`, `polygon_centroid`, `polygon_bbox`;
- `is_ring_closed`, `close_ring`;
- `detect_self_intersections`;
- `ring_orientation`, `normalize_polygon_orientation`.

Point-in-polygon uses ray casting with explicit boundary checks through `on_segment`. Holes are handled by first testing the outer ring, then excluding points inside any hole.

Complexity:

- Point in polygon: `O(V)` where `V` is total ring vertices.
- Area and centroid: `O(V)`.
- Self-intersection detection: `O(E^2)` for a ring with `E` edges. This is correct for small lab cases; large city datasets should combine it with a spatial index.

### Polyline

Implemented in `app/geometry_kernel/polyline.py`.

Projection functions work in a local equirectangular meter plane around the query point:

- `point_to_segment_projection`;
- `point_to_polyline_projection`;
- `polyline_length`;
- `cumulative_lengths`;
- `interpolate_along_polyline`;
- `cut_polyline_at_distance`;
- `split_polyline_at_points`;
- `heading_at_distance`.

Projection returns:

```python
ProjectionResult(
    projected_point=(lon, lat),
    distance_m=...,
    segment_index=...,
    t=...,
    offset_distance=...,
    along_track_distance=...,
)
```

The old compatibility aliases `projection` and `distance` are preserved.

Complexity:

- Segment projection: `O(1)`.
- Polyline projection: `O(n)`.
- Cumulative lengths: `O(n)`.
- Split by points: `O(n + k log k)` in practice, after projecting each split point over the polyline.

### Corridor

Implemented in `app/geometry_kernel/corridor.py`.

- `polyline_corridor_bbox`;
- `approximate_polyline_buffer`;
- `corridor_contains_point`;
- `road_corridor_debug_geojson`.

The current corridor buffer is a conservative expanded bbox around the polyline, plus an exact point-to-polyline distance check for containment. It is suitable for broad-phase filtering and debug visualization. It is not a full offset-curve buffer and will over-include near bends, long diagonals, and concave corridor shapes.

### Simplification

Implemented in `app/geometry_kernel/simplification.py`.

- `douglas_peucker`;
- `visvalingam_whyatt`;
- `simplify_polyline_with_error_report`.

The error report includes:

- `original_point_count`;
- `simplified_point_count`;
- `compression_ratio`;
- `max_error_estimate`;
- `method`.

Complexity:

- Douglas-Peucker: worst-case `O(n^2)`, typical `O(n log n)`.
- Visvalingam-Whyatt with heap: `O(n log n)`.
- Max error estimate against simplified polyline: `O(nm)` for `n` original points and `m` simplified segments.

## Degenerate Case Table

| Case | Handling |
| --- | --- |
| Collinear triples | `orientation` returns `COLLINEAR` using scale-aware tolerance. |
| Near-collinear large coordinates | `robust_orientation` recomputes ambiguous determinants with `Decimal`. |
| Endpoint-touch segments | Classified as `kind="point"`, `relation="endpoint_touch"`. |
| T-junction segments | Classified as `kind="point"`, `relation="touch"`. |
| Overlapping segments | Classified as `kind="overlap"` with ordered overlap endpoints. |
| Reversed overlapping segments | Normalized along the dominant axis before returning overlap. |
| Parallel disjoint segments | Classified as `relation="disjoint"` or `"collinear_disjoint"`. |
| Polygon boundary point | Respects boundary policy. |
| Polygon with hole | Hole interior returns `"outside"`; hole boundary follows boundary policy. |
| Self-intersecting ring | `detect_self_intersections` reports segment indexes and debug geometry. |
| Duplicate polyline points | Projection skips zero-length segments when a better segment exists. |
| Zero-length segment | Projection returns the endpoint with `t=0`. |
| Tiny-angle polyline | Simplification keeps the breakpoint when perpendicular error exceeds tolerance. |
| Empty geometry | Functions either return empty output where meaningful or raise clear `ValueError`. |

## Degenerate Case Gallery

The gallery dataset lives at `datasets/synthetic/geometry_degenerate_cases.json`. It is a small, explicit regression corpus for geometry cases that often break road-network algorithms:

- collinear and near-collinear predicates;
- endpoint, T-junction, overlap, reversed-overlap, and almost-parallel segment relations;
- polygon holes and bowtie self-intersections;
- duplicate polyline points, zero-length segments, and tiny-angle simplification;
- road-like crossing and overlap cases used by topology repair.

Programmatic usage:

```python
from app.geometry_kernel.case_gallery import load_geometry_cases, run_all_geometry_cases

cases = load_geometry_cases()
result = run_all_geometry_cases(cases)
assert result["summary"]["pass_rate"] >= 0.95
```

CLI usage:

```bash
python -m scripts.run_geometry_cases
```

The CLI prints total/pass/fail counts and writes combined debug GeoJSON to `docs/assets/geometry_case_debug_layers.geojson`. The same data is exposed through FastAPI:

- `GET /geometry/cases`
- `POST /geometry/cases/run`
- `POST /geometry/cases/run-all`

## Difference From Shapely and PostGIS

Shapely/GEOS and PostGIS are production-grade geometry engines with exacting standards, rich geometry models, and years of optimization. HDMap-Lab does not try to replace them. The kernel exists to make the algorithmic decisions visible:

- how orientation is computed;
- how endpoint and overlap cases are classified;
- how topology repair distinguishes crossing, touching, and overlapping roads;
- how debug layers are produced for the React workbench;
- how benchmarks can compare a self-developed algorithm against external baselines.

Shapely and PostGIS are kept as optional baseline comparisons in this project, not as replacements for the core implementation.

## Examples

```python
from app.geometry_kernel.intersection import segment_intersection
from app.geometry_kernel.polygon import point_in_polygon
from app.geometry_kernel.polyline import point_to_polyline_projection
from app.geometry_kernel.simplification import simplify_polyline_with_error_report

intersection = segment_intersection((0, 0), (2, 0), (1, -1), (1, 0))
assert intersection.kind == "point"
assert intersection.relation == "touch"

polygon = [
    [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)],
    [(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)],
]
assert point_in_polygon((2, 2), polygon) == "outside"

projection = point_to_polyline_projection((116.4, 39.901), [(116.39, 39.9), (116.41, 39.9)])
print(projection.projected_point, projection.distance_m, projection.along_track_distance)

report = simplify_polyline_with_error_report([(0, 0), (0.001, 0.0001), (0.002, 0)], tolerance_m=5)
print(report.to_dict())
```

## Tests

Run the phase 1 geometry tests:

```bash
python -m pytest tests/test_geometry_kernel.py tests/test_geometry_kernel_predicates.py tests/test_geometry_kernel_intersection.py tests/test_geometry_kernel_polygon.py tests/test_geometry_kernel_polyline.py tests/test_geometry_kernel_simplification.py
python -m ruff check app tests
```
