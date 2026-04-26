from __future__ import annotations

import argparse
from pathlib import Path

from app.core.geojson import feature_collection
from app.storage.osm_loader import geocode_place_bbox, load_osm_online_bbox


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a small OSM road sample and save it as GeoJSON.")
    parser.add_argument("--place", default="Tsinghua University, Beijing")
    parser.add_argument("--output", default="datasets/osm_samples/sample.geojson")
    args = parser.parse_args()

    bbox = geocode_place_bbox(args.place)
    _, roads = load_osm_online_bbox(bbox)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        _to_json(feature_collection(road.to_geojson_feature() for road in roads)),
        encoding="utf-8",
    )
    print(f"saved {len(roads)} roads to {output}")


def _to_json(payload: dict) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
