from __future__ import annotations

from benchmarks.city_scale_benchmark import render_markdown, run_city_scale_benchmark


def test_city_scale_benchmark_report_shape() -> None:
    features = [
        {
            "type": "Feature",
            "id": "road_1",
            "properties": {},
            "geometry": {"type": "LineString", "coordinates": [[116.0, 39.0], [116.001, 39.0]]},
        },
        {
            "type": "Feature",
            "id": "road_2",
            "properties": {},
            "geometry": {"type": "LineString", "coordinates": [[116.0, 39.001], [116.001, 39.001]]},
        },
    ]
    report = run_city_scale_benchmark(features, query_count=3, seed=1)
    markdown = render_markdown(report)

    assert report["dataset"]["roads"] == 2
    assert len(report["results"]) == 5
    assert "City-Scale Spatial Index Benchmark Result" in markdown
