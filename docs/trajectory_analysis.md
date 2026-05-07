# Trajectory Analysis v2

HDMap-Lab trajectory analysis is a geometry toolbox for comparing GPS traces, simplifying paths, finding outliers, and detecting route deviation.

## Fréchet Distance

`discrete_frechet_distance(path_a, path_b)` measures similarity while respecting point order. It is useful when the path shape and traversal order both matter.

The implementation uses dynamic programming:

```text
ca(i,j) = max(distance(a_i, b_j), min(ca(i-1,j), ca(i-1,j-1), ca(i,j-1)))
```

`frechet_matching_pairs` also returns a monotone matching path and a witness pair as GeoJSON debug layers.

Complexity: `O(n*m)` time and memory.

## Hausdorff Distance

`hausdorff_distance(path_a, path_b)` measures the largest nearest-neighbor miss between two point sets. It does not preserve traversal order, so it is good for geometric coverage checks but not sequence alignment.

`hausdorff_witness_points` returns the point pair responsible for the distance.

Complexity: `O(n*m)` time and `O(1)` extra memory.

## DTW

Dynamic Time Warping aligns trajectories with variable sampling rates.

```python
dtw_distance(path_a, path_b, window=10)
dtw_alignment_path(path_a, path_b)
```

The distance function is configurable; by default it uses haversine distance. A Sakoe-Chiba style `window` can limit alignment drift.

Complexity: `O(n*m)` without a window and `O(n*w)` with a window.

## Simplification

Trajectory simplification reuses the geometry kernel:

- `simplify_trajectory_rdp`: Douglas-Peucker.
- `simplify_trajectory_vw`: Visvalingam-Whyatt.
- `simplification_error_report`: original count, simplified count, compression ratio, and max error estimate.

## Outlier Detection

The module exposes:

- `speed_outlier_detection`
- `angle_outlier_detection`
- `distance_jump_detection`
- `map_matching_residual_outlier_detection`

These are heuristic detectors. They are designed to produce inspectable debug candidates, not to replace sensor-fusion validation.

## Route Deviation

`route_deviation_detection(trajectory, reference_route)` projects each raw point to the reference polyline and reports:

- `deviation_segments`
- `max_deviation_m`
- `mean_deviation_m`
- `p95_deviation_m`
- `off_route_points`
- `debug_layers`

Debug layers include raw trajectory, reference route, off-route points, and residual lines.

## API

`POST /trajectory/analyze`

```json
{
  "trajectory": {
    "id": "trace_001",
    "points": [
      {"lon": 116.0, "lat": 39.0},
      {"lon": 116.001, "lat": 39.0}
    ]
  },
  "reference_route": [[116.0, 39.0], [116.002, 39.0]],
  "methods": ["frechet", "hausdorff", "dtw", "simplification", "outlier", "deviation"],
  "return_debug_layers": true
}
```

## CLI

```bash
python -m scripts.analyze_trajectory \
  --trajectory datasets/synthetic/trajectory.json \
  --reference datasets/synthetic/reference_route.geojson \
  --output docs/assets/trajectory_analysis_result.json
```

The input can be a coordinate array, a JSON object with `trajectory`, a GeoJSON Feature, a LineString, or a FeatureCollection containing a LineString.

## Current Limits

- The distance functions operate on sampled points; continuous Fréchet is not implemented.
- All distances use local haversine calculations and do not model map projection distortion in detail.
- Outlier thresholds are heuristics and should be tuned per sensor/sampling rate.
- Route deviation assumes the reference route is already in the same coordinate system and order.
