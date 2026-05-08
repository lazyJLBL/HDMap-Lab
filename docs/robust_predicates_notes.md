# Robust Predicate Notes

HDMap-Lab uses a small pure-Python geometry kernel because the project is meant to show the computational geometry decisions, not hide them behind GEOS/PostGIS.

## Why Floating Point Geometry Fails

Core predicates such as orientation compute a determinant:

```text
(bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
```

This becomes fragile when:

- three points are nearly collinear and the determinant is close to zero;
- coordinates are large but local road-network offsets are small;
- segment endpoints are repeated or nearly repeated;
- two products are large and nearly cancel each other.

Those cases are common in road data: snapped intersections, duplicate edges, parallel service roads, tiny connector segments, and imported OSM/GeoJSON coordinates with mixed precision.

## Current Strategy

`app/geometry_kernel/predicates.py` uses:

- translated determinants, so orientation is evaluated relative to point `a`;
- `EPSILON = 1e-12` for point and bbox comparisons;
- scale-aware tolerance based on local coordinate span and floating-point machine epsilon;
- `exact_orientation_fallback` for ambiguous near-zero orientation values.

The fallback recomputes the determinant with high-precision `Decimal` values converted through `str(value)`. This is slower than the float path, so it is only used when `orientation_value` is inside the computed tolerance band.

## Scope Boundary

This approach is appropriate for small-area lon/lat road-network experiments, such as city districts or campus-scale extracts, where coordinates are close together and the goal is stable topology classification.

It is not a complete exact arithmetic kernel. It does not provide symbolic exact predicates, robust polygon overlay, or full geodesic geometry. If the original float has already lost the input precision, `Decimal(str(value))` cannot reconstruct it.

## Risk Cases

The current kernel should be treated carefully for:

- global-scale coordinates mixed with millimeter-level offsets;
- extremely long segments crossing large coordinate ranges;
- invalid polygons with self-overlap and holes touching boundaries;
- repeated topology repair passes that accumulate tiny coordinate changes;
- imported data with inconsistent coordinate precision;
- cases where legal/commercial GIS correctness is required.

For production GIS, compare against GEOS/PostGIS and use exact-predicate libraries where correctness guarantees matter more than keeping the algorithm implementation visible.
