# Release Checklist

Verification date: 2026-05-08 03:05 +08:00

## Required Commands

| Command | Result | Notes |
| --- | --- | --- |
| `python -m pip install -r requirements.txt` | Passed | Runtime dependencies only after requirements split. |
| `python -m ruff check app tests benchmarks scripts` | Passed | `All checks passed!` |
| `python -m pytest` | Passed | 134 tests passed. |
| `cd frontend && npm ci` | Passed | 75 packages installed. |
| `cd frontend && npm run build` | Passed | TypeScript and Vite production build passed. |
| `docker build -t hdmap-lab:local .` | Blocked by environment/network | Initial failure: Docker Desktop Linux engine pipe missing. After starting Docker Desktop, build reached Dockerfile step 1 but failed fetching `python:3.12-slim` auth token from Docker Hub due network timeout. |

## Additional Verification

| Command | Result | Notes |
| --- | --- | --- |
| `python -m pip install -r requirements-dev.txt` | Passed | Installs runtime, bench, pytest, pytest-cov, ruff, mypy, httpx. |
| `python -m pytest --cov=app --cov=benchmarks --cov=scripts --cov-report=term-missing` | Passed | 134 tests passed, total coverage summary: 76%. |
| `python -m scripts.prepare_osm_extract --input-geojson data/roads.geojson --output datasets/osm_samples/local_demo_roads.geojson --summary-output docs/assets/real_osm_extract_summary.json` | Passed | Prepared 13 local demo roads and wrote summary. The generated GeoJSON is ignored by git; the summary is committed. |
| `python -m benchmarks.spatial_index_benchmark --dataset osm_roads_sample --items 100000 --queries 100 --indexes brute_force,grid,quadtree,rtree,str_rtree,kdtree --query-types bbox --output docs/assets/real_osm_spatial_index_benchmark.json` | Passed | Generated local toy/sample GeoJSON benchmark report with brute-force correctness checks. |
| `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` | Passed | Backend served `/health` with `status=ok`, 13 roads, 9 nodes, 1 trajectory. |
| `cd frontend && npm run dev -- --host 127.0.0.1 --port 5173` | Passed | Frontend returned HTTP 200 through Vite dev server. |
| Playwright capture of Repair / Stress Test / Index Bench | Passed | Generated `screenshot-topology-repair.png`, `screenshot-mapmatching-stress.png`, and `screenshot-spatial-benchmark.png`. |

## Failures and Fixes

- HMM map matching weights were ineffective because `match_hmm` deleted `heading_weight` and `road_class_weight`, while `cost_breakdown` hardcoded heading, road class, turn, oneway, layer, and speed costs.
  - Fix: added `HMMCostWeights`, wired weights through `match_hmm`, `cost_breakdown`, `/mapmatch`, and `/benchmarks/map-matching`.
  - Test: `tests/test_hmm_matcher_v2.py::test_hmm_weight_overrides_change_reported_match_cost`.
- Robust predicate fallback existed only inside `robust_orientation`.
  - Fix: exposed `exact_orientation_fallback` and documented the tolerance/fallback boundary.
  - Tests: added large-coordinate small-offset and extremely short segment cases.
- Runtime dependencies previously included dev, bench, and PostGIS packages.
  - Fix: split `requirements.txt`, `requirements-dev.txt`, `requirements-bench.txt`, and `requirements-postgis.txt`; CI now installs dev deps explicitly.
- Docker build remains unresolved in this local environment.
  - Fix attempted: started Docker Desktop successfully.
  - Remaining blocker: Docker Hub token/base-image fetch timed out before the project Dockerfile could build. Re-run after Docker Hub/network access is available or after pre-pulling `python:3.12-slim`.

## Current Scope Notes

- Fresh developer environments should install `requirements-dev.txt` before running lint and tests. `requirements.txt` is now intentionally runtime-only.
- The committed OSM/GeoJSON benchmark result is a toy/local sample with 13 road segments, not a city-scale result.
- README now describes this as a city-scale-capable benchmark generator plus reproducible local report.
- OpenDRIVE/Lanelet2 and PostGIS comparison remain prototype-level.
- Demo visual tracking is documented in `docs/assets/demo_visuals.md`; dirty repair, HMM stress, and spatial benchmark screenshots are real captures from the running app.
