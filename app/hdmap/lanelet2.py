from __future__ import annotations

import xml.etree.ElementTree as ET

from app.hdmap.lane import Lane, LaneBoundary
from app.models.point import Coordinate


def import_lanelet2_xml(xml_text: str) -> tuple[list[Lane], list[LaneBoundary]]:
    root = ET.fromstring(xml_text)
    raw_nodes: dict[str, Coordinate] = {}
    for node in root.findall("node"):
        raw_nodes[node.attrib["id"]] = (float(node.attrib["lon"]), float(node.attrib["lat"]))

    ways: dict[str, tuple[list[Coordinate], dict[str, str]]] = {}
    for way in root.findall("way"):
        refs = [nd.attrib["ref"] for nd in way.findall("nd") if nd.attrib.get("ref") in raw_nodes]
        tags = {tag.attrib.get("k", ""): tag.attrib.get("v", "") for tag in way.findall("tag")}
        ways[way.attrib["id"]] = ([raw_nodes[ref] for ref in refs], tags)

    boundaries: dict[str, LaneBoundary] = {}
    lanes: list[Lane] = []
    for relation in root.findall("relation"):
        tags = {tag.attrib.get("k", ""): tag.attrib.get("v", "") for tag in relation.findall("tag")}
        if tags.get("type") != "lanelet":
            continue
        members = {member.attrib.get("role", ""): member.attrib.get("ref", "") for member in relation.findall("member")}
        left_id = members.get("left")
        right_id = members.get("right")
        centerline_id = members.get("centerline")
        left_boundary = _boundary_from_way(left_id, ways, boundaries)
        right_boundary = _boundary_from_way(right_id, ways, boundaries)
        centerline = ways.get(centerline_id, ([], {}))[0] if centerline_id else []
        if not centerline and left_boundary and right_boundary:
            centerline = _average_boundaries(left_boundary.geometry, right_boundary.geometry)
        lane_id = relation.attrib.get("id", "lanelet")
        lanes.append(
            Lane(
                id=f"lanelet_{lane_id}",
                centerline=centerline,
                left_boundary=left_boundary.id if left_boundary else None,
                right_boundary=right_boundary.id if right_boundary else None,
                speed_limit=float(tags.get("speed_limit") or tags.get("maxspeed") or 40.0),
                turn_type=tags.get("turn_direction") or tags.get("subtype") or "through",
                predecessor_ids=_split_tag(tags.get("predecessor")),
                successor_ids=_split_tag(tags.get("successor")),
                metadata=tags,
            )
        )
    return lanes, list(boundaries.values())


def export_lanelet2_xml(lanes: list[Lane], boundaries: list[LaneBoundary]) -> str:
    root = ET.Element("osm", version="0.6", generator="HDMap-Lab")
    node_id = -1
    way_id = -1
    relation_id = -1
    way_ids: dict[str, str] = {}

    def add_way(identifier: str, coords: list[Coordinate], tags: dict[str, str]) -> str:
        nonlocal node_id, way_id
        way_ref = str(way_id)
        way_id -= 1
        way = ET.SubElement(root, "way", id=way_ref)
        for lon, lat in coords:
            node_ref = str(node_id)
            node_id -= 1
            ET.SubElement(root, "node", id=node_ref, lon=str(lon), lat=str(lat))
            ET.SubElement(way, "nd", ref=node_ref)
        ET.SubElement(way, "tag", k="hdmap_lab_id", v=identifier)
        for key, value in tags.items():
            ET.SubElement(way, "tag", k=key, v=value)
        way_ids[identifier] = way_ref
        return way_ref

    for boundary in boundaries:
        add_way(
            boundary.id,
            boundary.geometry,
            {"type": "line_thin", "subtype": boundary.boundary_type, "color": boundary.color},
        )
    for lane in lanes:
        centerline_ref = add_way(f"{lane.id}_centerline", lane.centerline, {"type": "centerline"})
        relation_ref = str(relation_id)
        relation_id -= 1
        relation = ET.SubElement(root, "relation", id=relation_ref)
        if lane.left_boundary and lane.left_boundary in way_ids:
            ET.SubElement(relation, "member", type="way", ref=way_ids[lane.left_boundary], role="left")
        if lane.right_boundary and lane.right_boundary in way_ids:
            ET.SubElement(relation, "member", type="way", ref=way_ids[lane.right_boundary], role="right")
        ET.SubElement(relation, "member", type="way", ref=centerline_ref, role="centerline")
        ET.SubElement(relation, "tag", k="type", v="lanelet")
        ET.SubElement(relation, "tag", k="hdmap_lab_id", v=lane.id)
        ET.SubElement(relation, "tag", k="speed_limit", v=str(lane.speed_limit))
        ET.SubElement(relation, "tag", k="turn_direction", v=lane.turn_type)
        if lane.predecessor_ids:
            ET.SubElement(relation, "tag", k="predecessor", v=",".join(lane.predecessor_ids))
        if lane.successor_ids:
            ET.SubElement(relation, "tag", k="successor", v=",".join(lane.successor_ids))
    return ET.tostring(root, encoding="unicode")


def _boundary_from_way(
    way_id: str | None,
    ways: dict[str, tuple[list[Coordinate], dict[str, str]]],
    boundaries: dict[str, LaneBoundary],
) -> LaneBoundary | None:
    if not way_id or way_id not in ways:
        return None
    if way_id not in boundaries:
        geometry, tags = ways[way_id]
        boundaries[way_id] = LaneBoundary(
            id=f"boundary_{way_id}",
            geometry=geometry,
            boundary_type=tags.get("subtype") or tags.get("type") or "unknown",
            color=tags.get("color") or "unknown",
        )
    return boundaries[way_id]


def _average_boundaries(left: list[Coordinate], right: list[Coordinate]) -> list[Coordinate]:
    count = min(len(left), len(right))
    return [((left[index][0] + right[index][0]) / 2.0, (left[index][1] + right[index][1]) / 2.0) for index in range(count)]


def _split_tag(value: str | None) -> list[str]:
    return [item for item in (value or "").split(",") if item]
