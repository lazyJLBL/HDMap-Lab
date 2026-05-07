from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.geometry_kernel.case_gallery import cases_to_feature_collection, load_geometry_cases, run_all_geometry_cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HDMap-Lab geometry degenerate case gallery.")
    parser.add_argument("--cases", type=Path, default=None, help="Optional path to a geometry case JSON file.")
    parser.add_argument(
        "--debug-output",
        type=Path,
        default=Path("docs/assets/geometry_case_debug_layers.geojson"),
        help="Path for combined debug GeoJSON layers.",
    )
    parser.add_argument("--json-output", type=Path, default=None, help="Optional path for full result JSON.")
    args = parser.parse_args()

    cases = load_geometry_cases(args.cases)
    payload = run_all_geometry_cases(cases)
    summary = payload["summary"]

    args.debug_output.parent.mkdir(parents=True, exist_ok=True)
    args.debug_output.write_text(json.dumps(cases_to_feature_collection(cases), indent=2), encoding="utf-8")

    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"total cases: {summary['total']}")
    print(f"passed: {summary['passed']}")
    print(f"failed: {summary['failed']}")
    if summary["failed_cases"]:
        print("failed cases:")
        for result in payload["results"]:
            if not result["passed"]:
                print(f"- {result['case_id']}: {'; '.join(result['reasons'])}")
    print(f"debug_layers: {args.debug_output}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
