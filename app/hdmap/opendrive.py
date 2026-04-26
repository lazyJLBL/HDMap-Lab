from __future__ import annotations

import xml.etree.ElementTree as ET

from app.hdmap.lane import Lane, LaneBoundary
from app.models.point import Coordinate


def export_lanes_to_opendrive(lanes: list[Lane], boundaries: list[LaneBoundary] | None = None) -> str:
    root = ET.Element("OpenDRIVE")
    boundary_by_id = {boundary.id: boundary for boundary in boundaries or []}
    for lane in lanes:
        road = ET.SubElement(root, "road", id=lane.id, name=lane.id, length=str(_polyline_length_hint(lane.centerline)))
        user_data = ET.SubElement(road, "userData")
        vector_lane = ET.SubElement(
            user_data,
            "vectorLane",
            id=lane.id,
            speedLimit=str(lane.speed_limit),
            turnType=lane.turn_type,
            leftBoundary=lane.left_boundary or "",
            rightBoundary=lane.right_boundary or "",
            predecessors=",".join(lane.predecessor_ids),
            successors=",".join(lane.successor_ids),
        )
        _append_polyline(vector_lane, "centerline", lane.centerline)
        for boundary_id in [lane.left_boundary, lane.right_boundary]:
            if boundary_id and boundary_id in boundary_by_id:
                boundary = boundary_by_id[boundary_id]
                boundary_node = ET.SubElement(
                    vector_lane,
                    "boundary",
                    id=boundary.id,
                    boundaryType=boundary.boundary_type,
                    color=boundary.color,
                )
                _append_polyline(boundary_node, "geometry", boundary.geometry)
    return ET.tostring(root, encoding="unicode")


def import_opendrive_lanes(xml_text: str) -> list[Lane]:
    root = ET.fromstring(xml_text)
    lanes: list[Lane] = []
    for element in root.findall(".//vectorLane"):
        lanes.append(
            Lane(
                id=element.attrib.get("id", "lane"),
                centerline=_read_polyline(element.find("centerline")),
                left_boundary=element.attrib.get("leftBoundary") or None,
                right_boundary=element.attrib.get("rightBoundary") or None,
                speed_limit=float(element.attrib.get("speedLimit", 40.0)),
                turn_type=element.attrib.get("turnType", "through"),
                predecessor_ids=_split_ids(element.attrib.get("predecessors", "")),
                successor_ids=_split_ids(element.attrib.get("successors", "")),
            )
        )
    return lanes


def import_opendrive_stub(xml_text: str) -> list[Lane]:
    return import_opendrive_lanes(xml_text)


def _append_polyline(parent: ET.Element, tag: str, coords: list[Coordinate]) -> None:
    node = ET.SubElement(parent, tag)
    for index, (lon, lat) in enumerate(coords):
        ET.SubElement(node, "point", s=str(index), lon=str(lon), lat=str(lat))


def _read_polyline(node: ET.Element | None) -> list[Coordinate]:
    if node is None:
        return []
    return [(float(point.attrib["lon"]), float(point.attrib["lat"])) for point in node.findall("point")]


def _split_ids(value: str) -> list[str]:
    return [item for item in value.split(",") if item]


def _polyline_length_hint(coords: list[Coordinate]) -> float:
    return float(max(0, len(coords) - 1))
