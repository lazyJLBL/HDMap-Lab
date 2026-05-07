from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import RoadEdge, RoadNode
from app.topology import repair_topology


def make_dirty_network() -> tuple[list[RoadNode], list[RoadEdge]]:
    nodes = [
        RoadNode("a", 0.0, 0.0),
        RoadNode("b", 2.0, 0.0),
        RoadNode("c", 1.0, -1.0),
        RoadNode("d", 1.0, 1.0),
        RoadNode("b_near", 2.00000001, 0.0),
    ]
    roads = [
        RoadEdge("horizontal", "a", "b", [(0.0, 0.0), (2.0, 0.0)], 2.0),
        RoadEdge("vertical", "c", "d", [(1.0, -1.0), (1.0, 1.0)], 2.0),
        RoadEdge("duplicate", "a", "b_near", [(0.0, 0.0), (2.00000001, 0.0)], 2.0),
    ]
    return nodes, roads


def main() -> None:
    parser = argparse.ArgumentParser(description="Run HDMap-Lab topology repair benchmark on a dirty synthetic network.")
    parser.add_argument("--output", type=Path, default=Path("docs/assets/topology_repair_benchmark.json"))
    args = parser.parse_args()

    nodes, roads = make_dirty_network()
    started = time.perf_counter()
    result = repair_topology(nodes, roads, snap_tolerance_m=2.0)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    before_summary = result.before.to_dict()["summary"]
    after_summary = result.after.to_dict()["summary"]
    payload = {
        "dataset": "synthetic_dirty_crossing_duplicate",
        "elapsed_ms": elapsed_ms,
        "operations": result.operations,
        "before": before_summary,
        "after": after_summary,
        "correctness": {
            "duplicate_edges_removed": result.operations["duplicate_edges_removed"] >= 1,
            "illegal_crossings_repaired": after_summary["illegal_crossings"] == 0,
            "quality_score_improved": after_summary["quality_score"] >= before_summary["quality_score"],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_output = args.output.with_suffix(".md")
    markdown_output.write_text(render_markdown_report(payload), encoding="utf-8")
    print("| Metric | Value |")
    print("| --- | ---: |")
    print(f"| elapsed_ms | {elapsed_ms:.3f} |")
    for key, value in result.operations.items():
        print(f"| {key} | {value} |")
    for key, value in after_summary.items():
        print(f"| after_{key} | {value} |")
    print(f"output: {args.output} and {markdown_output}")


def render_markdown_report(payload: dict) -> str:
    lines = [
        "# Topology Repair Benchmark",
        "",
        f"- Dataset: `{payload['dataset']}`",
        f"- Elapsed: `{payload['elapsed_ms']:.3f} ms`",
        "",
        "## Correctness",
        "",
        "| Check | Passed |",
        "| --- | ---: |",
    ]
    for key, value in payload["correctness"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "## Before / After",
            "",
            "| Metric | Before | After |",
            "| --- | ---: | ---: |",
        ]
    )
    keys = sorted(set(payload["before"]) | set(payload["after"]))
    for key in keys:
        lines.append(f"| {key} | {payload['before'].get(key, '-')} | {payload['after'].get(key, '-')} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
