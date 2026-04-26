from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from app.core.bbox import bbox_intersects, bbox_of_coords
from app.geometry_kernel.intersection import segment_intersection
from app.geometry_kernel.predicates import same_point
from app.models import RoadEdge, RoadNode


@dataclass(slots=True)
class TopologyIssue:
    type: str
    severity: str
    message: str
    road_ids: list[str] = field(default_factory=list)
    node_ids: list[str] = field(default_factory=list)
    location: tuple[float, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "severity": self.severity,
            "message": self.message,
            "road_ids": self.road_ids,
            "node_ids": self.node_ids,
            "location": list(self.location) if self.location else None,
        }


@dataclass(slots=True)
class TopologyReport:
    components: list[list[str]]
    isolated_nodes: list[str]
    dangling_edges: list[str]
    duplicate_edges: list[tuple[str, str]]
    illegal_crossings: list[TopologyIssue]
    self_intersections: list[TopologyIssue]
    issues: list[TopologyIssue]

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "components": len(self.components),
                "isolated_nodes": len(self.isolated_nodes),
                "dangling_edges": len(self.dangling_edges),
                "duplicate_edges": len(self.duplicate_edges),
                "illegal_crossings": len(self.illegal_crossings),
                "self_intersections": len(self.self_intersections),
                "issues": len(self.issues),
            },
            "components": self.components,
            "isolated_nodes": self.isolated_nodes,
            "dangling_edges": self.dangling_edges,
            "duplicate_edges": [list(pair) for pair in self.duplicate_edges],
            "illegal_crossings": [issue.to_dict() for issue in self.illegal_crossings],
            "self_intersections": [issue.to_dict() for issue in self.self_intersections],
            "issues": [issue.to_dict() for issue in self.issues],
        }


def validate_topology(nodes: list[RoadNode], roads: list[RoadEdge]) -> TopologyReport:
    adjacency: dict[str, set[str]] = {node.id: set() for node in nodes}
    degree: dict[str, int] = defaultdict(int)
    for road in roads:
        adjacency.setdefault(road.from_node, set()).add(road.to_node)
        adjacency.setdefault(road.to_node, set()).add(road.from_node)
        degree[road.from_node] += 1
        degree[road.to_node] += 1

    components = _connected_components(adjacency)
    isolated_nodes = sorted(node_id for node_id in adjacency if degree[node_id] == 0)
    dangling_edges = sorted(
        road.id for road in roads if degree[road.from_node] <= 1 or degree[road.to_node] <= 1
    )
    duplicate_edges = _duplicate_edges(roads)
    self_intersections = _self_intersections(roads)
    illegal_crossings = _illegal_crossings(roads)

    issues: list[TopologyIssue] = []
    issues.extend(
        TopologyIssue("isolated_node", "warning", f"Node {node_id} is isolated", node_ids=[node_id])
        for node_id in isolated_nodes
    )
    issues.extend(
        TopologyIssue("dangling_edge", "warning", f"Road {road_id} has a dangling endpoint", road_ids=[road_id])
        for road_id in dangling_edges
    )
    issues.extend(
        TopologyIssue("duplicate_edge", "error", f"Roads {first} and {second} are duplicate", road_ids=[first, second])
        for first, second in duplicate_edges
    )
    issues.extend(self_intersections)
    issues.extend(illegal_crossings)
    return TopologyReport(
        components=components,
        isolated_nodes=isolated_nodes,
        dangling_edges=dangling_edges,
        duplicate_edges=duplicate_edges,
        illegal_crossings=illegal_crossings,
        self_intersections=self_intersections,
        issues=issues,
    )


def _connected_components(adjacency: dict[str, set[str]]) -> list[list[str]]:
    seen: set[str] = set()
    components: list[list[str]] = []
    for start in adjacency:
        if start in seen:
            continue
        queue: deque[str] = deque([start])
        seen.add(start)
        component: list[str] = []
        while queue:
            node = queue.popleft()
            component.append(node)
            for next_node in adjacency.get(node, set()):
                if next_node not in seen:
                    seen.add(next_node)
                    queue.append(next_node)
        components.append(sorted(component))
    components.sort(key=len, reverse=True)
    return components


def _duplicate_edges(roads: list[RoadEdge]) -> list[tuple[str, str]]:
    seen: dict[tuple[tuple[float, float], tuple[float, float]], str] = {}
    duplicates: list[tuple[str, str]] = []
    for road in roads:
        start = _rounded(road.geometry[0])
        end = _rounded(road.geometry[-1])
        key = tuple(sorted([start, end]))  # type: ignore[assignment]
        if key in seen:
            duplicates.append((seen[key], road.id))
        else:
            seen[key] = road.id
    return duplicates


def _self_intersections(roads: list[RoadEdge]) -> list[TopologyIssue]:
    issues: list[TopologyIssue] = []
    for road in roads:
        segments = list(zip(road.geometry, road.geometry[1:], strict=False))
        for first_index, (a1, a2) in enumerate(segments):
            for second_index, (b1, b2) in enumerate(segments[first_index + 2 :], start=first_index + 2):
                if first_index == 0 and second_index == len(segments) - 1 and same_point(a1, b2):
                    continue
                intersection = segment_intersection(a1, a2, b1, b2)
                if intersection.intersects:
                    issues.append(
                        TopologyIssue(
                            "self_intersection",
                            "error",
                            f"Road {road.id} self-intersects",
                            road_ids=[road.id],
                            location=intersection.point,
                        )
                    )
    return issues


def _illegal_crossings(roads: list[RoadEdge]) -> list[TopologyIssue]:
    issues: list[TopologyIssue] = []
    for index, first in enumerate(roads):
        first_bbox = bbox_of_coords(first.geometry)
        for second in roads[index + 1 :]:
            if first.from_node in {second.from_node, second.to_node} or first.to_node in {second.from_node, second.to_node}:
                continue
            if not bbox_intersects(first_bbox, bbox_of_coords(second.geometry)):
                continue
            for a1, a2 in zip(first.geometry, first.geometry[1:], strict=False):
                for b1, b2 in zip(second.geometry, second.geometry[1:], strict=False):
                    intersection = segment_intersection(a1, a2, b1, b2)
                    if intersection.kind == "point" and intersection.point is not None:
                        if any(same_point(intersection.point, endpoint) for endpoint in (a1, a2, b1, b2)):
                            continue
                        issues.append(
                            TopologyIssue(
                                "illegal_crossing",
                                "error",
                                f"Roads {first.id} and {second.id} cross without a shared node",
                                road_ids=[first.id, second.id],
                                location=intersection.point,
                            )
                        )
                    elif intersection.kind == "overlap":
                        issues.append(
                            TopologyIssue(
                                "overlapping_roads",
                                "error",
                                f"Roads {first.id} and {second.id} overlap",
                                road_ids=[first.id, second.id],
                                location=intersection.overlap[0] if intersection.overlap else None,
                            )
                        )
    return issues


def _rounded(point: tuple[float, float], digits: int = 7) -> tuple[float, float]:
    return (round(point[0], digits), round(point[1], digits))
