from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.geojson import feature_collection
from app.geometry_kernel.intersection import segment_intersection
from app.geometry_kernel.polyline import polyline_length
from app.geometry_kernel.predicates import same_point
from app.models import RoadEdge, RoadNode
from app.models.point import Coordinate
from app.topology.snapping import snap_close_nodes
from app.topology.validation import TopologyReport, validate_topology


@dataclass(slots=True)
class TopologyRepairResult:
    nodes: list[RoadNode]
    roads: list[RoadEdge]
    before: TopologyReport
    after: TopologyReport
    operations: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "operations": self.operations,
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "fixed_roads": feature_collection(road.to_geojson_feature() for road in self.roads),
            "topology_report": self.after.to_dict(),
        }


def repair_topology(
    nodes: list[RoadNode],
    roads: list[RoadEdge],
    snap_tolerance_m: float = 1.0,
) -> TopologyRepairResult:
    before = validate_topology(nodes, roads)
    snapped_nodes, snapped_roads, mapping = snap_close_nodes(nodes, roads, snap_tolerance_m)
    split_roads = _split_roads_at_intersections(snapped_roads)
    deduped_roads, duplicates_removed = _remove_duplicate_edges(split_roads)
    repaired_nodes = _nodes_from_roads(deduped_roads, snapped_nodes)
    after = validate_topology(repaired_nodes, deduped_roads)
    operations = {
        "snapped_nodes": sum(1 for source, target in mapping.items() if source != target),
        "split_edges_added": max(0, len(split_roads) - len(snapped_roads)),
        "duplicate_edges_removed": duplicates_removed,
        "merged_collinear_roads": 0,
    }
    return TopologyRepairResult(repaired_nodes, deduped_roads, before, after, operations)


def _split_roads_at_intersections(roads: list[RoadEdge]) -> list[RoadEdge]:
    split_points: dict[str, list[Coordinate]] = {road.id: [] for road in roads}
    for index, first in enumerate(roads):
        for second in roads[index + 1 :]:
            for a1, a2 in zip(first.geometry, first.geometry[1:], strict=False):
                for b1, b2 in zip(second.geometry, second.geometry[1:], strict=False):
                    intersection = segment_intersection(a1, a2, b1, b2)
                    if intersection.kind != "point" or intersection.point is None:
                        continue
                    point = intersection.point
                    if any(same_point(point, endpoint) for endpoint in (a1, a2, b1, b2)):
                        continue
                    split_points[first.id].append(point)
                    split_points[second.id].append(point)

    result: list[RoadEdge] = []
    for road in roads:
        points = _dedupe_points(split_points[road.id])
        if not points:
            result.append(road)
            continue
        chain = _insert_split_points(road.geometry, points)
        for index, (start, end) in enumerate(zip(chain, chain[1:], strict=False)):
            if same_point(start, end):
                continue
            geometry = [start, end]
            result.append(
                _copy_road(
                    road,
                    id=f"{road.id}_split_{index}",
                    from_node=_node_id(start),
                    to_node=_node_id(end),
                    geometry=geometry,
                    length=polyline_length(geometry),
                    metadata={**(road.metadata or {}), "source_edge": road.id},
                )
            )
    return result


def _insert_split_points(polyline: list[Coordinate], points: list[Coordinate]) -> list[Coordinate]:
    chain: list[Coordinate] = []
    for start, end in zip(polyline, polyline[1:], strict=False):
        if not chain:
            chain.append(start)
        candidates = [
            point
            for point in points
            if _point_on_segment_bbox(point, start, end) and not same_point(point, start) and not same_point(point, end)
        ]
        candidates.sort(key=lambda point: _segment_t(point, start, end))
        chain.extend(candidates)
        chain.append(end)
    return _dedupe_points(chain)


def _remove_duplicate_edges(roads: list[RoadEdge]) -> tuple[list[RoadEdge], int]:
    seen: set[tuple[tuple[float, float], tuple[float, float]]] = set()
    result: list[RoadEdge] = []
    removed = 0
    for road in roads:
        start = (round(road.geometry[0][0], 7), round(road.geometry[0][1], 7))
        end = (round(road.geometry[-1][0], 7), round(road.geometry[-1][1], 7))
        key = tuple(sorted([start, end]))  # type: ignore[assignment]
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        result.append(road)
    return result, removed


def _nodes_from_roads(roads: list[RoadEdge], fallback_nodes: list[RoadNode]) -> list[RoadNode]:
    nodes: dict[str, RoadNode] = {node.id: node for node in fallback_nodes}
    for road in roads:
        start = road.geometry[0]
        end = road.geometry[-1]
        nodes[road.from_node] = RoadNode(road.from_node, start[0], start[1])
        nodes[road.to_node] = RoadNode(road.to_node, end[0], end[1])
    return list(nodes.values())


def _point_on_segment_bbox(point: Coordinate, start: Coordinate, end: Coordinate) -> bool:
    return (
        min(start[0], end[0]) - 1e-12 <= point[0] <= max(start[0], end[0]) + 1e-12
        and min(start[1], end[1]) - 1e-12 <= point[1] <= max(start[1], end[1]) + 1e-12
    )


def _segment_t(point: Coordinate, start: Coordinate, end: Coordinate) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    denom = dx * dx + dy * dy
    if denom <= 1e-24:
        return 0.0
    return ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / denom


def _dedupe_points(points: list[Coordinate]) -> list[Coordinate]:
    result: list[Coordinate] = []
    for point in points:
        if not any(same_point(point, existing) for existing in result):
            result.append(point)
    return result


def _node_id(coord: Coordinate) -> str:
    return f"node_{coord[0]:.7f}_{coord[1]:.7f}".replace(".", "_").replace("-", "m")


def _copy_road(road: RoadEdge, **changes) -> RoadEdge:
    values = {
        "id": road.id,
        "from_node": road.from_node,
        "to_node": road.to_node,
        "geometry": road.geometry,
        "length": road.length,
        "speed_limit": road.speed_limit,
        "road_type": road.road_type,
        "oneway": road.oneway,
        "direction": road.direction,
        "road_class": road.road_class,
        "lane_count": road.lane_count,
        "turn_restrictions": road.turn_restrictions,
        "metadata": road.metadata,
    }
    values.update(changes)
    return RoadEdge(**values)
