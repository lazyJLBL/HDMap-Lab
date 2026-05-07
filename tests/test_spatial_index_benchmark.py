from __future__ import annotations

import json

from benchmarks.spatial_index_benchmark import run_spatial_index_benchmark


def test_spatial_index_benchmark_outputs_required_metrics(tmp_path) -> None:
    output = tmp_path / "spatial_index_benchmark.json"
    payload = run_spatial_index_benchmark(
        dataset="synthetic_clustered",
        item_count=200,
        query_count=20,
        index_types=["brute", "grid", "kdtree", "quadtree", "rtree", "str_rtree", "morton"],
        query_types=["bbox", "radius", "nearest"],
        output=output,
        return_debug_layers=True,
    )

    assert output.exists()
    assert output.with_suffix(".md").exists()
    assert payload["results"]
    assert payload["debug_layers"]["items_sample"]["type"] == "FeatureCollection"

    required = {
        "build_time_ms",
        "query_count",
        "p50_ms",
        "p95_ms",
        "p99_ms",
        "max_ms",
        "avg_candidate_count",
        "false_positive_rate",
        "recall",
        "memory_estimate_bytes",
        "index_stats",
    }
    for row in payload["results"]:
        assert required <= row.keys()
        assert row["recall"] == 1.0
        assert row["false_positive_rate"] == 0.0

    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["dataset"] == "synthetic_clustered"
    assert len(saved["results"]) == len(payload["results"])
