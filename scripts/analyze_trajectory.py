from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.models.point import Coordinate
from app.trajectory import analyze_trajectory


def load_coordinates(path: str | Path) -> list[Coordinate]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [(float(item[0]), float(item[1])) for item in payload]
    if "trajectory" in payload:
        return [(float(item[0]), float(item[1])) for item in payload["trajectory"]]
    if payload.get("type") == "FeatureCollection":
        for feature in payload.get("features", []):
            coords = _coords_from_geometry(feature.get("geometry", {}))
            if coords:
                return coords
    if payload.get("type") == "Feature":
        return _coords_from_geometry(payload.get("geometry", {}))
    if payload.get("type") == "LineString":
        return _coords_from_geometry(payload)
    raise ValueError(f"Cannot extract trajectory coordinates from {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a trajectory with HDMap-Lab trajectory v2 metrics.")
    parser.add_argument("--trajectory", required=True)
    parser.add_argument("--reference")
    parser.add_argument("--output", default="docs/assets/trajectory_analysis_result.json")
    parser.add_argument("--methods", default="frechet,hausdorff,dtw,simplification,outlier,deviation")
    parser.add_argument("--simplify-tolerance-m", type=float, default=5.0)
    parser.add_argument("--deviation-threshold-m", type=float, default=30.0)
    args = parser.parse_args()

    trajectory = load_coordinates(args.trajectory)
    reference = load_coordinates(args.reference) if args.reference else None
    result = analyze_trajectory(
        trajectory,
        reference=reference,
        simplify_tolerance_m=args.simplify_tolerance_m,
        deviation_threshold_m=args.deviation_threshold_m,
        methods=[item.strip() for item in args.methods.split(",") if item.strip()],
        return_debug_layers=True,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"points={result['point_count']} length_m={result['length_m']:.2f}")
    print(f"wrote {output}")


def _coords_from_geometry(geometry: dict[str, Any]) -> list[Coordinate]:
    if geometry.get("type") == "LineString":
        return [(float(item[0]), float(item[1])) for item in geometry.get("coordinates", [])]
    if geometry.get("type") == "MultiLineString":
        return [(float(item[0]), float(item[1])) for line in geometry.get("coordinates", []) for item in line]
    if geometry.get("type") == "Point":
        coord = geometry.get("coordinates", [])
        return [(float(coord[0]), float(coord[1]))] if len(coord) >= 2 else []
    return []


if __name__ == "__main__":
    main()
