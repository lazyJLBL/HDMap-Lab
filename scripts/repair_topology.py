from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.geojson import feature_collection
from app.storage.geojson_loader import load_roads_geojson
from app.topology.repair import repair_topology


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair dirty road topology and write fixed GeoJSON/report files.")
    parser.add_argument("--input", required=True, type=Path, help="Input road GeoJSON FeatureCollection.")
    parser.add_argument("--output", required=True, type=Path, help="Output repaired road GeoJSON path.")
    parser.add_argument("--report", required=True, type=Path, help="Output topology repair report JSON path.")
    parser.add_argument("--snap-tolerance-m", type=float, default=1.0)
    parser.add_argument("--merge-collinear", action="store_true")
    parser.add_argument("--dangling-mode", choices=["mark_only", "remove_short", "remove_all"], default="mark_only")
    parser.add_argument("--dangling-length-threshold-m", type=float, default=10.0)
    parser.add_argument("--no-split-intersections", action="store_true")
    parser.add_argument("--ignore-layers", action="store_true")
    args = parser.parse_args()

    nodes, roads = load_roads_geojson(args.input)
    result = repair_topology(
        nodes,
        roads,
        snap_tolerance_m=args.snap_tolerance_m,
        split_intersections=not args.no_split_intersections,
        merge_collinear=args.merge_collinear,
        dangling_mode=args.dangling_mode,
        dangling_length_threshold_m=args.dangling_length_threshold_m,
        respect_layers=not args.ignore_layers,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(feature_collection(road.to_geojson_feature() for road in result.roads), indent=2),
        encoding="utf-8",
    )
    args.report.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    print(f"input roads: {len(roads)}")
    print(f"output roads: {len(result.roads)}")
    print(f"operations: {json.dumps(result.operations, indent=2)}")
    print(f"output: {args.output}")
    print(f"report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
