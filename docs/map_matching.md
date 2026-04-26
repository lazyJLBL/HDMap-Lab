# Map Matching

Map Matching maps noisy GPS trajectory points to road network edges.

## Input

- A trajectory: ordered GPS points in `[lon, lat]`
- A road network: `RoadEdge` geometries and graph connectivity
- Algorithm: `nearest`, `candidate_cost`, or `hmm`

## Output

- matched road sequence
- per-point matched road id
- projection point on the road
- distance and optional confidence/cost fields

## Nearest Road Matching

For every GPS point:

1. search nearby road candidates with R-Tree / KD-Tree
2. compute exact point-to-polyline distance
3. choose the closest road

This is fast and easy to explain, but it can fail around intersections, parallel roads, and overpasses.

## Candidate Cost Matching

Each GPS point keeps multiple road candidates. The selected candidate minimizes:

```text
total_cost = distance_cost + direction_weight * direction_cost + connectivity_weight * connectivity_cost
```

- `distance_cost`: GPS point to road distance in meters
- `direction_cost`: trajectory heading vs road heading angle difference
- `connectivity_cost`: shortest path distance between adjacent candidate roads

This is more stable than nearest-road matching because it considers local trajectory continuity.

## HMM Matching

HMM treats the real road sequence as hidden states and GPS observations as emissions.

Emission probability:

```text
GPS point closer to candidate road -> higher probability
```

Transition probability:

```text
road-network distance between candidates close to GPS straight-line distance -> higher probability
```

Viterbi then finds the globally best candidate sequence:

```text
GPS Points -> Candidate Search -> Emission + Transition Scores -> Viterbi -> Road Sequence
```

## Known Failure Cases

- sparse GPS sampling
- severe GPS drift
- dense parallel roads
- overpasses without lane-level elevation metadata
- incomplete road connectivity

## Improvements

- use heading from device sensors when available
- add road class priors
- add turn penalties
- add speed feasibility checks
- support bidirectional candidate states explicitly

## Evaluation Upgrade

The upgraded matcher adds:

- heading consistency
- one-way direction handling
- turn penalty between candidate roads
- road-class prior
- transition path cost through the road graph
- synthetic GPS stress cases

Run:

```bash
python -m benchmarks.map_matching_benchmark
```

Or call:

```text
POST /benchmarks/map-matching
```

The report compares nearest matching and HMM with sequence precision, recall, confidence, and latency for failure cases such as parallel-road drift and low-frequency GPS.
