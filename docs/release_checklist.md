# Release Checklist

Last verification date: 2026-05-07

## Backend Test Status

- `python -m pip install -r requirements.txt`: passed. The shared Python environment still reports unrelated dependency warnings for globally installed packages that require older numpy/packaging/pillow versions.
- `python -m ruff check app tests benchmarks scripts`: passed.
- `python -m pytest`: passed, 131 tests.
- Added focused core tests:
  - `tests/test_geometry_degenerate_cases.py`
  - `tests/test_topology_repair_cases.py`
  - `tests/test_spatial_index_consistency.py`
  - `tests/test_map_matching_cases.py`
  - `tests/test_api_smoke.py`

## Frontend Build Status

- `cd frontend`
- `npm install`: passed.
- `npm run build`: passed after frontend workbench updates.
- Local dev server smoke:
  - Backend `http://127.0.0.1:8000/health`: passed.
  - Frontend `http://127.0.0.1:5173`: returned HTTP 200.

## Docker Status

- `docker compose config`: passed.
- `docker compose up --build`: failed because the local Docker Desktop Linux engine pipe was unavailable:

```text
open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified
```

This is an environment issue consistent with Docker Desktop / Docker Engine not running. Re-run after starting Docker Desktop.

## Benchmark Status

- `python -m benchmarks.spatial_index_benchmark`: passed and generated `docs/assets/spatial_index_benchmark.json` plus Markdown.
- `python -m benchmarks.map_matching_benchmark`: passed and generated `docs/assets/map_matching_benchmark.json` plus Markdown.
- `python -m benchmarks.topology_repair_benchmark`: passed and generated `docs/assets/topology_repair_benchmark.json` plus Markdown.
- `python -m benchmarks.city_scale_benchmark --roads data/roads.geojson --queries 20 --output docs/city_scale_benchmark_result.md`: passed as a local sample-data smoke run.
- Spatial benchmark includes brute-force correctness fields.
- Map matching benchmark uses synthetic ground-truth sequences.
- Topology repair benchmark writes JSON and Markdown reports.
- City-scale benchmark is a local-data generator and should not be presented as a committed city-scale result.

## README Status

- Rewritten around the project main line.
- Quick Start commands match local project structure.
- Completed / Prototype / Planned status is separated.
- OpenDRIVE/Lanelet2 and city-scale benchmark are explicitly scoped as prototype/generator features.

## Documentation Status

- `docs/resume_bullets.md`: updated.
- `docs/interview_notes.md`: updated.
- `docs/demo_script.md`: added.
- `docs/benchmark_guide.md`: added.
- Algorithm-specific docs already exist under `docs/`.

## Screenshot Status

- Existing assets are present under `docs/assets/`, including `demo.gif` and several screenshot PNG files.
- No new screenshot was generated in this pass.

## Known Limitations

- Docker service startup was not verified because Docker Engine was unavailable locally.
- Default data is sample/synthetic/toy data.
- OpenDRIVE/Lanelet2 support is prototype-level.
- Benchmark results depend on local data scale, query distribution, Python runtime, and hardware.
- Geometry assumptions target small-area lon/lat road-network experiments.

## Next Step Plan

1. Start Docker Desktop and re-run `docker compose up --build`.
2. Capture updated frontend screenshots for dirty repair, spatial benchmark, and HMM matching.
3. If using city-scale claims, generate a real report from a local OSM/GeoJSON extract and document the dataset size.
