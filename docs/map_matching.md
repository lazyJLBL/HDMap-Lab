# Map Matching v2

`app/map_matching/` maps noisy GPS trajectory points onto a road network. The v2 implementation is a benchmarkable HMM stress-test system with explicit candidate features, cost breakdowns, synthetic failure cases, and debug layers for the frontend.

## Input and Output

Input:

- ordered GPS trajectory points;
- `RoadEdge` geometries and road graph connectivity;
- algorithm: `nearest`, `candidate_cost`, or `hmm`;
- candidate parameters: `k`, `radius_m`, optional heading/class/layer filters.

HMM output:

```json
{
  "trajectory_id": "parallel_roads_drift",
  "algorithm": "hmm",
  "matched_road_sequence": [],
  "confidence": 0.0,
  "matches": [],
  "candidates": [],
  "chosen_path": [],
  "metrics": {},
  "debug_layers": {}
}
```

Each match includes the chosen road, projected point, candidate list, and cost breakdown.

## Candidate Search

`CandidateSearcher.search` combines R-tree bbox prefiltering and KD-tree centroid fallback. For each road candidate it computes exact point-to-polyline projection using the geometry kernel.

Candidate fields:

- `road_id`;
- `projected_point`;
- `distance_m`;
- `segment_index`;
- `t`;
- `heading_diff`;
- `road_class`;
- `layer`;
- `is_oneway_compatible`;
- `score_features`.

Complexity: candidate search is `O(log R + C * P)` in normal indexed cases, where `R` is roads, `C` candidate roads, and `P` average road vertices. Fallback can degrade toward `O(R * P)`.

## HMM Model

Let `z_t` be the hidden road candidate at GPS observation `o_t`.

The HMM objective is:

```text
argmax_z P(z_1) * product P(o_t | z_t) * product P(z_t | z_{t-1})
```

In implementation this is minimized as additive costs:

```text
total = emission
      + transition
      + heading
      + speed
      + turn
      + road_class
      + oneway
      + layer
```

The implementation exposes these terms through `HMMCostWeights`:

| Weight | Default | Effect |
| --- | ---: | --- |
| `emission_weight` | 1.0 | Scales GPS-to-road projection distance. Higher values make the matcher trust per-point geometry more. |
| `transition_weight` | 1.0 | Scales graph-continuity distance between consecutive candidates. Higher values discourage disconnected or physically implausible jumps. |
| `heading_weight` | 4.0 | Scales trajectory heading vs road heading. Higher values favor roads aligned with motion direction. |
| `turn_weight` | 2.0 | Scales turn angle between consecutive candidate roads. Higher values prefer smoother paths. |
| `road_class_weight` | 5.0 | Scales road-class prior. Higher values favor major roads over service/local roads in ambiguous cases. |
| `oneway_weight` | 25.0 | Penalty for choosing a candidate incompatible with one-way direction. |
| `layer_weight` | 6.0 | Penalty for jumping between road layers, such as surface road vs bridge/tunnel metadata. |
| `speed_weight` | 1.0 | Scales observed-speed feasibility between samples. |

`cost_breakdown` returns weighted components. This makes API and benchmark results explainable: changing a weight should change the reported cost and may change the selected path when candidates are close.

### Emission

Emission uses GPS-to-road distance:

```text
emission_cost = 0.5 * (distance_m / sigma)^2
```

Closer candidates have lower cost.

### Transition

Transition compares graph distance between consecutive candidate roads with straight-line GPS distance:

```text
transition_cost = abs(network_distance - gps_distance) / beta
```

Disconnected transitions receive a large penalty.

### Additional Penalties

- `heading`: trajectory heading vs road heading. For two-way roads the matcher accepts either travel direction; for one-way roads it compares against the legal direction only.
- `turn`: angular change between candidate roads. This helps avoid zig-zagging through candidates that happen to be close to noisy GPS points.
- `road_class`: prior favoring higher-class roads when GPS evidence is ambiguous. It is deliberately a prior, not a hard rule.
- `oneway`: large penalty for incompatible direction. It can be set lower for experiments but defaults high enough to make violations visible.
- `layer`: penalty for jumping between surface/bridge/tunnel layers when metadata is present.
- `speed`: observed speed feasibility between samples, based on GPS distance and `step_seconds` when available.

## Viterbi

The matcher builds candidate layers per GPS point and runs dynamic programming:

```text
dp[t][candidate] = min_previous(dp[t-1][previous] + transition(previous, candidate) + emission(candidate))
```

Backpointers recover the chosen road sequence. `beam_width` can prune each layer to the best-scoring candidates. If a candidate layer is empty, the matcher returns a clear fallback result instead of crashing.

Complexity: `O(T * K^2 * G)` where `T` is GPS points, `K` candidates per point, and `G` is graph shortest-path cost for transition distance. For small benchmark cases this is explicit and inspectable; large-scale production systems cache or approximate transition distances.

## Nearest vs HMM

Nearest matching selects the closest road per point. It is fast but fails when:

- GPS drift moves points closer to a parallel road;
- sparse sampling jumps across intersections;
- a bridge and surface road cross in 2D;
- a one-way road is geometrically close but directionally invalid.

HMM uses sequence context, road class priors, heading, transition continuity, oneway, and layer penalties, so it can recover from per-point nearest mistakes.

## Synthetic Stress Cases

`app/map_matching/synthetic.py` supports:

- `straight_clean`;
- `parallel_roads_drift`;
- `low_frequency_sampling`;
- `urban_canyon_drift`;
- `intersection_ambiguity`;
- `overpass_layer_confusion`;
- `wrong_nearest_road`;
- `gps_outliers`;
- `missing_points`;
- `u_turn_case`;
- `one_way_violation_case`.

Each case returns roads, trajectory, ground-truth road sequence, noise config, and debug layers.

## Evaluation Metrics

`app/map_matching/evaluation.py` computes:

- `sequence_accuracy`;
- `precision`;
- `recall`;
- `f1`;
- `edit_distance`;
- `route_length_error`;
- `matched_point_error_mean`;
- `matched_point_error_p95`;
- `continuity_score`;
- `illegal_transition_count`;
- `latency_ms`;
- `candidate_count_avg`.

## Benchmark

CLI:

```bash
python -m benchmarks.map_matching_benchmark \
  --cases parallel_roads_drift,low_frequency_sampling,overpass_layer_confusion \
  --algorithms nearest,hmm \
  --output docs/assets/map_matching_benchmark.json
```

API:

```text
POST /benchmarks/map-matching
```

Request:

```json
{
  "cases": ["parallel_roads_drift", "low_frequency_sampling"],
  "algorithms": ["nearest", "hmm"],
  "noise_sigma_m": 4.0,
  "sampling_interval": 1,
  "k": 5,
  "radius_m": 150.0,
  "sigma": 20.0,
  "beta": 50.0,
  "emission_weight": 1.0,
  "transition_weight": 1.0,
  "heading_weight": 4.0,
  "turn_weight": 2.0,
  "road_class_weight": 5.0,
  "oneway_weight": 25.0,
  "layer_weight": 6.0,
  "speed_weight": 1.0,
  "return_debug_layers": true
}
```

`POST /mapmatch` accepts the same HMM weight fields when `algorithm` is `"hmm"`. `nearest` and `candidate_cost` ignore these HMM-only weights.

The benchmark JSON is generated from live code. Do not copy numbers into docs unless the JSON file exists and was produced by the benchmark command.

## Current Limitations

- Transition distance currently calls graph shortest path directly; no transition cache yet.
- Candidate states are road-level, not lane-level.
- GPS coordinates use local metric approximations suitable for lab-scale examples.
- The synthetic benchmark is designed to expose algorithm behavior; it is not a substitute for real fleet GPS data.
- Layer handling relies on road metadata and does not infer bridge/tunnel semantics from geometry alone.
