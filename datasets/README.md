# Datasets

`datasets/` holds the upgraded experiment datasets:

- `toy/`: tiny deterministic fixtures for unit tests and topology repair demos.
- `synthetic/`: generated GPS traces with noise, drift, low-frequency sampling, and known ground truth.
- `osm_samples/`: local OSM extracts. Large extracts are ignored by git; use `python -m scripts.download_osm_sample`.

The original runnable demo data remains in `data/` for backward compatibility.
