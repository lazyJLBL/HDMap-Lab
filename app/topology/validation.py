from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Literal

from app.core.bbox import bbox_intersects, bbox_of_coords
from app.core.geojson import feature_collection
from app.geometry_kernel.intersection import segment_intersection
from app.geometry_kernel.polyline import angle_difference, bearing, point_to_segment_projection
from app.geometry_kernel.predicates import same_point
from app.models import RoadEdge, RoadNode
from app.models.point import Coordinate

Severity = Literal["info", "warning", "error", "critical"]


@dataclass(slots=True)
class TopologyIssue:
    type: str
    severity: Severity
    message: str
    road_ids: list[str] = field(default_factory=list)
    node_ids: list[str] = field(default_factory=list)
    coordinate: Coordinate | None = None
    suggested_fix: str = ""
    debug_geojson: dict[str, Any] | None = None
    id: str = ""

    @property
    def location(self) -> Coordinate | None:
        return self.coordinate

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "severity": self.severity,
            "message": self.message,
            "road_ids": self.road_ids,
            "node_ids": self.node_ids,
            "coordinate": list(self.coordinate) if self.coordinate else None,
            "location": list(self.coordinate) if self.coordinate else None,
            "suggested_fix": self.suggested_fix,
            "debug_geojson": self.debug_geojson or _empty_feature_collection(),
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
    metrics: dict[str, Any] = field(default_factory=dict)
    debug_layers: dict[str, Any] = field(default_factory=dict)
    quality_score: float = 100.0

    def to_dict(self) -> dict[str, Any]:
        summary = {
            "node_count": self.metrics.get("node_count", 0),
            "edge_count": self.metrics.get("edge_count", 0),
            "components": len(self.components),
            "connected_components": len(self.components),
            "largest_component_ratio": self.metrics.get("largest_component_ratio", 0.0),
            "isolated_nodes": len(self.isolated_nodes),
            "dangling_edges": len(self.dangling_edges),
            "duplicate_edges": len(self.duplicate_edges),
            "illegal_crossings": len(self.illegal_crossings),
            "crossing_without_node": len(self.illegal_crossings),
            "self_intersections": len(self.self_intersections),
            "issues": len(self.issues),
            "quality_score": self.quality_score,
        }
        return {
            "summary": summary,
            "components": self.components,
            "isolated_nodes": self.isolated_nodes,
            "dangling_edges": self.dangling_edges,
            "duplicate_edges": [list(pair) for pair in self.duplicate_edges],
            "illegal_crossings": [issue.to_dict() for issue in self.illegal_crossings],
            "self_intersections": [issue.to_dict() for issue in self.self_intersections],
            "issues": [issue.to_dict() for issue in self.issues],
            "metrics": self.metrics,
            "debug_layers": self.debug_layers,
            "quality_score": self.quality_score,
        }


def validate_topology(
    nodes: list[RoadNode],
    roads: list[RoadEdge],
    detect_crossings: bool = True,
    detect_overlaps: bool = True,
    detect_near_miss: bool = False,
    near_miss_tolerance_m: float = 1.0,
    respect_layers: bool = True,
    return_debug_layers: bool = True,
) -> TopologyReport:
    node_by_id = {node.id: node for node in nodes}
    adjacency, directed_adjacency, reverse_directed = _build_adjacency(nodes, roads)
    degree = _degree(roads, adjacency)
    components = _connected_components(adjacency)
    isolated_nodes = sorted(node_id for node_id in adjacency if degree[node_id] == 0)
    dangling_edges = sorted(road.id for road in roads if degree[road.from_node] <= 1 or degree[road.to_node] <= 1)
    duplicate_edges, reverse_duplicate_edges = _duplicate_edges(roads)

    issues: list[TopologyIssue] = []
    issues.extend(
        _issue(
            "isolated_node",
            "warning",
            f"Node {node_id} is isolated",
            node_ids=[node_id],
            coordinate=node_by_id[node_id].coordinate if node_id in node_by_id else None,
            suggested_fix="Remove the node or connect it to a road edge.",
        )
        for node_id in isolated_nodes
    )
    issues.extend(
        _issue(
            "dangling_edge",
            "warning",
            f"Road {road.id} has a dangling endpoint",
            road_ids=[road.id],
            coordinate=road.geometry[0] if road.geometry else None,
            suggested_fix="Mark as intentional dead-end or remove short stubs during repair.",
            debug_geojson=feature_collection([_road_feature(road, "dangling_edge")]),
        )
        for road in roads
        if road.id in dangling_edges
    )
    issues.extend(
        _issue(
            "duplicate_edge",
            "error",
            f"Roads {first} and {second} are duplicate",
            road_ids=[first, second],
            suggested_fix="Deduplicate geometrically identical edges while preserving richer metadata.",
        )
        for first, second in duplicate_edges
    )
    issues.extend(
        _issue(
            "reverse_duplicate_edge",
            "warning",
            f"Roads {first} and {second} are reverse duplicates",
            road_ids=[first, second],
            suggested_fix="Keep both only if they represent legal opposite one-way roads.",
        )
        for first, second in reverse_duplicate_edges
    )

    geometry_issues = _geometry_issues(roads, respect_layers, detect_crossings, detect_overlaps, detect_near_miss, near_miss_tolerance_m)
    semantic_issues = _semantic_issues(roads)
    sharp_angle_issues = _sharp_angle_issues(roads, degree)
    one_way_issues = _oneway_dead_end_issues(roads, directed_adjacency, reverse_directed)
    issues.extend(geometry_issues)
    issues.extend(semantic_issues)
    issues.extend(sharp_angle_issues)
    issues.extend(one_way_issues)

    _assign_issue_ids(issues)
    illegal_crossings = [issue for issue in issues if issue.type == "crossing_without_node"]
    self_intersections = [issue for issue in issues if issue.type == "self_intersecting_road"]
    metrics = _metrics(
        nodes,
        roads,
        components,
        isolated_nodes,
        degree,
        duplicate_edges,
        reverse_duplicate_edges,
        directed_adjacency,
        reverse_directed,
        issues,
    )
    quality_score = _quality_score(issues)
    debug_layers = _debug_layers(issues, roads) if return_debug_layers else {}
    return TopologyReport(
        components=components,
        isolated_nodes=isolated_nodes,
        dangling_edges=dangling_edges,
        duplicate_edges=duplicate_edges,
        illegal_crossings=illegal_crossings,
        self_intersections=self_intersections,
        issues=issues,
        metrics=metrics,
        debug_layers=debug_layers,
        quality_score=quality_score,
    )


def _build_adjacency(
    nodes: list[RoadNode],
    roads: list[RoadEdge],
) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, set[str]]]:
    adjacency: dict[str, set[str]] = {node.id: set() for node in nodes}
    directed: dict[str, set[str]] = {node.id: set() for node in nodes}
    reverse_directed: dict[str, set[str]] = {node.id: set() for node in nodes}
    for road in roads:
        adjacency.setdefault(road.from_node, set()).add(road.to_node)
        adjacency.setdefault(road.to_node, set()).add(road.from_node)
        directed.setdefault(road.from_node, set()).add(road.to_node)
        reverse_directed.setdefault(road.to_node, set()).add(road.from_node)
        directed.setdefault(road.to_node, set())
        reverse_directed.setdefault(road.from_node, set())
        if not road.oneway:
            directed[road.to_node].add(road.from_node)
            reverse_directed[road.from_node].add(road.to_node)
    return adjacency, directed, reverse_directed


def _degree(roads: list[RoadEdge], adjacency: dict[str, set[str]]) -> dict[str, int]:
    degree: dict[str, int] = defaultdict(int)
    for node_id in adjacency:
        degree[node_id] = 0
    for road in roads:
        degree[road.from_node] += 1
        degree[road.to_node] += 1
    return degree


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


def _duplicate_edges(roads: list[RoadEdge]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    seen_undirected: dict[tuple[tuple[float, float], ...], str] = {}
    seen_directed: dict[tuple[tuple[float, float], ...], str] = {}
    duplicates: list[tuple[str, str]] = []
    reverse_duplicates: list[tuple[str, str]] = []
    for road in roads:
        if not road.geometry:
            continue
        directed_key = tuple(_rounded(point) for point in road.geometry)
        reverse_key = tuple(reversed(directed_key))
        undirected_key = min(directed_key, reverse_key)
        if directed_key in seen_directed:
            duplicates.append((seen_directed[directed_key], road.id))
        elif reverse_key in seen_directed:
            reverse_duplicates.append((seen_directed[reverse_key], road.id))
        elif undirected_key in seen_undirected:
            duplicates.append((seen_undirected[undirected_key], road.id))
        seen_directed[directed_key] = road.id
        seen_undirected[undirected_key] = road.id
    return duplicates, reverse_duplicates


def _geometry_issues(
    roads: list[RoadEdge],
    respect_layers: bool,
    detect_crossings: bool,
    detect_overlaps: bool,
    detect_near_miss: bool,
    near_miss_tolerance_m: float,
) -> list[TopologyIssue]:
    issues: list[TopologyIssue] = []
    for road in roads:
        issues.extend(_road_internal_geometry_issues(road))

    for index, first in enumerate(roads):
        if not first.geometry:
            continue
        first_bbox = bbox_of_coords(first.geometry)
        for second in roads[index + 1 :]:
            if not second.geometry:
                continue
            if respect_layers and _road_layer_key(first) != _road_layer_key(second):
                continue
            if first.from_node in {second.from_node, second.to_node} or first.to_node in {second.from_node, second.to_node}:
                continue
            if not bbox_intersects(first_bbox, bbox_of_coords(second.geometry)):
                if detect_near_miss:
                    near_miss = _near_miss_issue(first, second, near_miss_tolerance_m)
                    if near_miss:
                        issues.append(near_miss)
                continue
            for a1, a2 in zip(first.geometry, first.geometry[1:], strict=False):
                for b1, b2 in zip(second.geometry, second.geometry[1:], strict=False):
                    intersection = segment_intersection(a1, a2, b1, b2)
                    if intersection.kind == "point" and intersection.point is not None and detect_crossings:
                        if any(same_point(intersection.point, endpoint) for endpoint in (a1, a2, b1, b2)):
                            continue
                        issues.append(
                            _issue(
                                "crossing_without_node",
                                "error",
                                f"Roads {first.id} and {second.id} cross without a shared node",
                                road_ids=[first.id, second.id],
                                coordinate=intersection.point,
                                suggested_fix="Split both roads at the crossing if they are on the same layer.",
                                debug_geojson=feature_collection(
                                    [
                                        _road_feature(first, "crossing_without_node"),
                                        _road_feature(second, "crossing_without_node"),
                                        _point_feature(intersection.point, "crossing_without_node"),
                                    ]
                                ),
                            )
                        )
                    elif intersection.kind == "overlap" and detect_overlaps:
                        issues.append(
                            _issue(
                                "overlapping_roads",
                                "error",
                                f"Roads {first.id} and {second.id} overlap",
                                road_ids=[first.id, second.id],
                                coordinate=intersection.overlap[0] if intersection.overlap else None,
                                suggested_fix="Deduplicate or split overlapping road centerlines.",
                                debug_geojson=feature_collection(
                                    [
                                        _road_feature(first, "overlapping_roads"),
                                        _road_feature(second, "overlapping_roads"),
                                    ]
                                ),
                            )
                        )
            if detect_near_miss:
                near_miss = _near_miss_issue(first, second, near_miss_tolerance_m)
                if near_miss:
                    issues.append(near_miss)
    return issues


def _road_internal_geometry_issues(road: RoadEdge) -> list[TopologyIssue]:
    issues: list[TopologyIssue] = []
    if not road.geometry:
        issues.append(
            _issue(
                "missing_geometry",
                "critical",
                f"Road {road.id} has no geometry",
                road_ids=[road.id],
                suggested_fix="Drop the edge or provide a valid LineString geometry.",
            )
        )
        return issues
    seen_points: list[Coordinate] = []
    for point in road.geometry:
        if any(same_point(point, existing) for existing in seen_points):
            issues.append(
                _issue(
                    "duplicated_points_in_road",
                    "warning",
                    f"Road {road.id} contains duplicated coordinates",
                    road_ids=[road.id],
                    coordinate=point,
                    suggested_fix="Remove repeated coordinates before topology repair.",
                    debug_geojson=feature_collection([_point_feature(point, "duplicated_points_in_road")]),
                )
            )
            break
        seen_points.append(point)
    for index, (start, end) in enumerate(zip(road.geometry, road.geometry[1:], strict=False)):
        if same_point(start, end):
            issues.append(
                _issue(
                    "zero_length_segment",
                    "error",
                    f"Road {road.id} has a zero-length segment at index {index}",
                    road_ids=[road.id],
                    coordinate=start,
                    suggested_fix="Remove duplicated consecutive points or drop the edge.",
                    debug_geojson=feature_collection([_point_feature(start, "zero_length_segment")]),
                )
            )

    segments = list(zip(road.geometry, road.geometry[1:], strict=False))
    for first_index, (a1, a2) in enumerate(segments):
        for second_index, (b1, b2) in enumerate(segments[first_index + 2 :], start=first_index + 2):
            if first_index == 0 and second_index == len(segments) - 1 and same_point(a1, b2):
                continue
            intersection = segment_intersection(a1, a2, b1, b2)
            if intersection.intersects:
                issues.append(
                    _issue(
                        "self_intersecting_road",
                        "error",
                        f"Road {road.id} self-intersects",
                        road_ids=[road.id],
                        coordinate=intersection.point or (intersection.overlap[0] if intersection.overlap else None),
                        suggested_fix="Split or redraw the self-crossing road geometry.",
                        debug_geojson=feature_collection([_road_feature(road, "self_intersecting_road")]),
                    )
                )
    return issues


def _near_miss_issue(first: RoadEdge, second: RoadEdge, tolerance_m: float) -> TopologyIssue | None:
    best: tuple[float, Coordinate] | None = None
    for point in [*first.geometry, *second.geometry]:
        target_segments = second.geometry if point in first.geometry else first.geometry
        for start, end in zip(target_segments, target_segments[1:], strict=False):
            projection = point_to_segment_projection(point, start, end)
            if same_point(projection.projected_point, start) or same_point(projection.projected_point, end):
                continue
            candidate = (projection.distance_m, projection.projected_point)
            if best is None or candidate[0] < best[0]:
                best = candidate
    if best is None or best[0] > tolerance_m:
        return None
    return _issue(
        "near_miss_intersection",
        "warning",
        f"Roads {first.id} and {second.id} nearly meet within {best[0]:.2f} m",
        road_ids=[first.id, second.id],
        coordinate=best[1],
        suggested_fix="Snap endpoints or insert a connector if this is a real junction.",
        debug_geojson=feature_collection(
            [_road_feature(first, "near_miss_intersection"), _road_feature(second, "near_miss_intersection")]
        ),
    )


def _semantic_issues(roads: list[RoadEdge]) -> list[TopologyIssue]:
    issues: list[TopologyIssue] = []
    for road in roads:
        metadata = road.metadata or {}
        if road.speed_limit <= 0 or road.speed_limit > 160:
            issues.append(
                _issue(
                    "invalid_speed",
                    "warning",
                    f"Road {road.id} has suspicious speed {road.speed_limit}",
                    road_ids=[road.id],
                    suggested_fix="Normalize speed metadata to a plausible kph value.",
                )
            )
        if not road.road_class:
            issues.append(
                _issue(
                    "missing_road_class",
                    "warning",
                    f"Road {road.id} is missing road_class",
                    road_ids=[road.id],
                    suggested_fix="Infer road_class from highway/functional class metadata.",
                )
            )
        layer = metadata.get("layer", 0)
        try:
            int(layer)
        except (TypeError, ValueError):
            issues.append(
                _issue(
                    "invalid_layer",
                    "warning",
                    f"Road {road.id} has invalid layer {layer!r}",
                    road_ids=[road.id],
                    suggested_fix="Use an integer layer where 0 is surface level.",
                )
            )
        bridge = bool(metadata.get("bridge", False))
        tunnel = bool(metadata.get("tunnel", False))
        if bridge and tunnel:
            issues.append(
                _issue(
                    "inconsistent_bridge_tunnel_layer",
                    "error",
                    f"Road {road.id} is both bridge and tunnel",
                    road_ids=[road.id],
                    suggested_fix="Keep only the correct grade-separation flag.",
                )
            )
        if road.oneway and road.direction == "both":
            issues.append(
                _issue(
                    "oneway_metadata_conflict",
                    "warning",
                    f"Road {road.id} is oneway but direction is both",
                    road_ids=[road.id],
                    suggested_fix="Set direction to forward or reverse.",
                )
            )
    return issues


def _sharp_angle_issues(roads: list[RoadEdge], degree: dict[str, int]) -> list[TopologyIssue]:
    by_node: dict[str, list[tuple[RoadEdge, float]]] = defaultdict(list)
    for road in roads:
        if len(road.geometry) < 2:
            continue
        by_node[road.from_node].append((road, bearing(road.geometry[0], road.geometry[1])))
        by_node[road.to_node].append((road, bearing(road.geometry[-1], road.geometry[-2])))
    issues: list[TopologyIssue] = []
    for node_id, headings in by_node.items():
        if degree[node_id] < 2:
            continue
        for i, (_, first_heading) in enumerate(headings):
            for _, second_heading in headings[i + 1 :]:
                diff = angle_difference(first_heading, second_heading)
                if 0 < diff < 15:
                    issues.append(
                        _issue(
                            "sharp_angle_node",
                            "info",
                            f"Node {node_id} has a sharp angle of {diff:.1f} degrees",
                            node_ids=[node_id],
                            suggested_fix="Check whether nearly parallel edges should be merged.",
                        )
                    )
                    break
    return issues


def _oneway_dead_end_issues(
    roads: list[RoadEdge],
    directed: dict[str, set[str]],
    reverse_directed: dict[str, set[str]],
) -> list[TopologyIssue]:
    if not any(road.oneway for road in roads):
        return []
    issues: list[TopologyIssue] = []
    for node_id in sorted(directed):
        if reverse_directed.get(node_id) and not directed.get(node_id):
            issues.append(
                _issue(
                    "one_way_dead_end",
                    "warning",
                    f"One-way flow reaches node {node_id} with no outgoing edge",
                    node_ids=[node_id],
                    suggested_fix="Verify one-way direction or add a legal outgoing connector.",
                )
            )
    return issues


def _metrics(
    nodes: list[RoadNode],
    roads: list[RoadEdge],
    components: list[list[str]],
    isolated_nodes: list[str],
    degree: dict[str, int],
    duplicate_edges: list[tuple[str, str]],
    reverse_duplicate_edges: list[tuple[str, str]],
    directed: dict[str, set[str]],
    reverse_directed: dict[str, set[str]],
    issues: list[TopologyIssue],
) -> dict[str, Any]:
    total_length = sum(max(road.length, 0.0) for road in roads)
    largest_component = len(components[0]) if components else 0
    node_count = len(set([node.id for node in nodes]) | set(degree))
    strongly_connected = _strongly_connected_components(directed, reverse_directed)
    return {
        "node_count": node_count,
        "edge_count": len(roads),
        "total_length_m": total_length,
        "avg_edge_length_m": total_length / len(roads) if roads else 0.0,
        "road_class_distribution": dict(Counter(road.road_class or "missing" for road in roads)),
        "speed_distribution": dict(Counter(str(int(road.speed_limit)) for road in roads)),
        "oneway_ratio": sum(1 for road in roads if road.oneway) / len(roads) if roads else 0.0,
        "connected_components": len(components),
        "weakly_connected_components": len(components),
        "strongly_connected_components": len(strongly_connected),
        "largest_component_ratio": largest_component / node_count if node_count else 1.0,
        "isolated_nodes": isolated_nodes,
        "unreachable_components": components[1:],
        "degree_distribution": dict(Counter(str(value) for value in degree.values())),
        "dead_end_nodes": sorted(node_id for node_id, value in degree.items() if value == 1),
        "suspicious_degree_high_nodes": sorted(node_id for node_id, value in degree.items() if value >= 6),
        "duplicate_edges": [list(pair) for pair in duplicate_edges],
        "reverse_duplicate_edges": [list(pair) for pair in reverse_duplicate_edges],
        "issue_counts_by_type": dict(Counter(issue.type for issue in issues)),
        "issue_counts_by_severity": dict(Counter(issue.severity for issue in issues)),
    }


def _strongly_connected_components(
    directed: dict[str, set[str]],
    reverse_directed: dict[str, set[str]],
) -> list[list[str]]:
    seen: set[str] = set()
    order: list[str] = []

    def dfs(node: str) -> None:
        seen.add(node)
        for neighbor in directed.get(node, set()):
            if neighbor not in seen:
                dfs(neighbor)
        order.append(node)

    for node in directed:
        if node not in seen:
            dfs(node)

    seen.clear()
    components: list[list[str]] = []

    def reverse_dfs(node: str, component: list[str]) -> None:
        seen.add(node)
        component.append(node)
        for neighbor in reverse_directed.get(node, set()):
            if neighbor not in seen:
                reverse_dfs(neighbor, component)

    for node in reversed(order):
        if node not in seen:
            component: list[str] = []
            reverse_dfs(node, component)
            components.append(sorted(component))
    components.sort(key=len, reverse=True)
    return components


def _quality_score(issues: list[TopologyIssue]) -> float:
    penalty = 0.0
    weights = {"critical": 10.0, "error": 5.0, "warning": 2.0, "info": 0.5}
    for issue in issues:
        penalty += weights[issue.severity]
    return max(0.0, round(100.0 - penalty, 2))


def _debug_layers(issues: list[TopologyIssue], roads: list[RoadEdge]) -> dict[str, Any]:
    layers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    road_by_id = {road.id: road for road in roads}
    for issue in issues:
        if issue.coordinate:
            layers[issue.type].append(_point_feature(issue.coordinate, issue.type, issue.severity))
        for road_id in issue.road_ids:
            if road_id in road_by_id:
                layers[issue.type].append(_road_feature(road_by_id[road_id], issue.type, issue.severity))
    return {name: feature_collection(features) for name, features in layers.items()}


def _assign_issue_ids(issues: list[TopologyIssue]) -> None:
    counts: dict[str, int] = defaultdict(int)
    for issue in issues:
        counts[issue.type] += 1
        issue.id = f"{issue.type}_{counts[issue.type]:04d}"


def _issue(
    issue_type: str,
    severity: Severity,
    message: str,
    road_ids: list[str] | None = None,
    node_ids: list[str] | None = None,
    coordinate: Coordinate | None = None,
    suggested_fix: str = "",
    debug_geojson: dict[str, Any] | None = None,
) -> TopologyIssue:
    return TopologyIssue(
        type=issue_type,
        severity=severity,
        message=message,
        road_ids=road_ids or [],
        node_ids=node_ids or [],
        coordinate=coordinate,
        suggested_fix=suggested_fix,
        debug_geojson=debug_geojson,
    )


def _road_layer_key(road: RoadEdge) -> tuple[Any, bool, bool]:
    metadata = road.metadata or {}
    return metadata.get("layer", 0), bool(metadata.get("bridge", False)), bool(metadata.get("tunnel", False))


def _rounded(point: Coordinate, digits: int = 7) -> tuple[float, float]:
    return round(point[0], digits), round(point[1], digits)


def _road_feature(road: RoadEdge, layer: str, severity: str | None = None) -> dict[str, Any]:
    feature = road.to_geojson_feature()
    feature["properties"]["layer"] = layer
    if severity:
        feature["properties"]["severity"] = severity
    return feature


def _point_feature(point: Coordinate, layer: str, severity: str | None = None) -> dict[str, Any]:
    properties: dict[str, Any] = {"layer": layer}
    if severity:
        properties["severity"] = severity
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {"type": "Point", "coordinates": [point[0], point[1]]},
    }


def _empty_feature_collection() -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": []}
