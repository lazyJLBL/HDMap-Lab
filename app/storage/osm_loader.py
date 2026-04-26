from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from app.core.geometry import polyline_length
from app.models import RoadEdge, RoadNode

HIGHWAY_SPEEDS = {
    "motorway": 100.0,
    "trunk": 80.0,
    "primary": 60.0,
    "secondary": 50.0,
    "tertiary": 45.0,
    "residential": 35.0,
    "service": 20.0,
    "living_street": 15.0,
}


def _parse_speed(value: str | None, road_type: str) -> float:
    if not value:
        return HIGHWAY_SPEEDS.get(road_type, 40.0)
    match = re.search(r"\d+(\.\d+)?", value)
    return float(match.group(0)) if match else HIGHWAY_SPEEDS.get(road_type, 40.0)


def load_osm_file(path: str | Path) -> tuple[list[RoadNode], list[RoadEdge]]:
    root = ET.parse(path).getroot()
    return _parse_osm_root(root)


def load_osm_xml(xml_text: str) -> tuple[list[RoadNode], list[RoadEdge]]:
    root = ET.fromstring(xml_text)
    return _parse_osm_root(root)


def load_osm_online_bbox(bbox: tuple[float, float, float, float]) -> tuple[list[RoadNode], list[RoadEdge]]:
    min_lon, min_lat, max_lon, max_lat = bbox
    query = f"""
    [out:xml][timeout:25];
    (
      way["highway"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    (._;>;);
    out body;
    """
    response = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query},
        headers={"User-Agent": "HDMap-Lab/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    return load_osm_xml(response.text)


def geocode_place_bbox(place: str) -> tuple[float, float, float, float]:
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": place, "format": "json", "limit": 1},
        headers={"User-Agent": "HDMap-Lab/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload:
        raise ValueError(f"No OSM place found for {place!r}")
    south, north, west, east = [float(value) for value in payload[0]["boundingbox"]]
    return west, south, east, north


def load_osm_online_place(place: str) -> tuple[list[RoadNode], list[RoadEdge]]:
    return load_osm_online_bbox(geocode_place_bbox(place))


def _parse_osm_root(root: ET.Element) -> tuple[list[RoadNode], list[RoadEdge]]:
    raw_nodes: dict[str, RoadNode] = {}
    for node in root.findall("node"):
        node_id = f"osm_node_{node.attrib['id']}"
        raw_nodes[node.attrib["id"]] = RoadNode(node_id, float(node.attrib["lon"]), float(node.attrib["lat"]))

    roads: list[RoadEdge] = []
    used_nodes: dict[str, RoadNode] = {}
    for way in root.findall("way"):
        tags = {tag.attrib.get("k"): tag.attrib.get("v") for tag in way.findall("tag")}
        road_type = tags.get("highway")
        if not road_type:
            continue
        refs = [nd.attrib["ref"] for nd in way.findall("nd") if nd.attrib.get("ref") in raw_nodes]
        if len(refs) < 2:
            continue
        oneway = tags.get("oneway") in {"yes", "true", "1"}
        speed = _parse_speed(tags.get("maxspeed"), road_type)
        for index, (start_ref, end_ref) in enumerate(zip(refs, refs[1:], strict=False)):
            start = raw_nodes[start_ref]
            end = raw_nodes[end_ref]
            used_nodes[start.id] = start
            used_nodes[end.id] = end
            geometry = [start.coordinate, end.coordinate]
            roads.append(
                RoadEdge(
                    id=f"osm_way_{way.attrib['id']}_{index}",
                    from_node=start.id,
                    to_node=end.id,
                    geometry=geometry,
                    length=polyline_length(geometry),
                    speed_limit=speed,
                    road_type=road_type,
                    oneway=oneway,
                    direction="forward" if oneway else "both",
                    road_class=road_type,
                    lane_count=int(tags.get("lanes") or 1),
                    metadata={key: value for key, value in tags.items() if value is not None},
                )
            )
    return list(used_nodes.values()), roads
