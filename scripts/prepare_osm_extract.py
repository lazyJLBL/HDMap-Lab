from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.core.bbox import bbox_of_coords
from app.core.geojson import feature_collection
from app.models import RoadEdge
from app.storage.geojson_loader import load_roads_geojson
from app.storage.osm_loader import geocode_place_bbox, load_osm_file, load_osm_online_bbox


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a road extract from OSM XML, online OSM, or GeoJSON.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input-geojson", help="Existing GeoJSON FeatureCollection with LineString roads.")
    source.add_argument("--input-osm", help="Existing .osm XML extract.")
    source.add_argument("--bbox", help="Online OSM bbox as min_lon,min_lat,max_lon,max_lat.")
    source.add_argument("--place", help="Online OSM place name resolved through Nominatim.")
    parser.add_argument("--output", default="datasets/osm_samples/prepared_roads.geojson")
    parser.add_argument("--summary-output", default="docs/assets/real_osm_extract_summary.json")
    parser.add_argument("--max-roads", type=int, default=0, help="Optional cap for quick local benchmark runs.")
    args = parser.parse_args()

    roads, source_description = _load_roads(args)
    if args.max_roads > 0:
        roads = roads[: args.max_roads]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(feature_collection(road.to_geojson_feature() for road in roads), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = summarize_roads(roads, source_description)
    summary_output = Path(args.summary_output)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"prepared {len(roads)} roads -> {output}")
    print(f"summary -> {summary_output}")


def summarize_roads(roads: list[RoadEdge], source_description: str) -> dict[str, Any]:
    boxes = [bbox_of_coords(road.geometry) for road in roads if road.geometry]
    bbox = _union_bbox(boxes)
    classes = Counter(road.road_class for road in roads)
    return {
        "source": source_description,
        "road_segments": len(roads),
        "bbox": list(bbox),
        "total_length_m": sum(road.length for road in roads),
        "road_classes": dict(sorted(classes.items())),
    }


def _load_roads(args: argparse.Namespace) -> tuple[list[RoadEdge], str]:
    if args.input_geojson:
        _nodes, roads = load_roads_geojson(args.input_geojson)
        return roads, f"GeoJSON file: {args.input_geojson}"
    if args.input_osm:
        _nodes, roads = load_osm_file(args.input_osm)
        return roads, f"OSM XML file: {args.input_osm}"
    if args.bbox:
        bbox = _parse_bbox(args.bbox)
        _nodes, roads = load_osm_online_bbox(bbox)
        return roads, f"OpenStreetMap Overpass bbox: {list(bbox)}"
    bbox = geocode_place_bbox(args.place)
    _nodes, roads = load_osm_online_bbox(bbox)
    return roads, f"OpenStreetMap Overpass place: {args.place} bbox={list(bbox)}"


def _parse_bbox(value: str) -> tuple[float, float, float, float]:
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("--bbox must contain four comma-separated values: min_lon,min_lat,max_lon,max_lat")
    min_lon, min_lat, max_lon, max_lat = parts
    if min_lon >= max_lon or min_lat >= max_lat:
        raise ValueError("--bbox must satisfy min_lon < max_lon and min_lat < max_lat")
    return min_lon, min_lat, max_lon, max_lat


def _union_bbox(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    if not boxes:
        return (0.0, 0.0, 0.0, 0.0)
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


if __name__ == "__main__":
    main()
