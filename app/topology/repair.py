from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Literal

from app.core.geojson import feature_collection
from app.geometry_kernel.intersection import segment_intersection
from app.geometry_kernel.polyline import bearing, haversine_distance, polyline_length
from app.geometry_kernel.predicates import same_point
from app.models import RoadEdge, RoadNode
from app.models.point import Coordinate
from app.topology.validation import TopologyReport, validate_topology

DanglingMode = Literal["mark_only", "remove_short", "remove_all"]


@dataclass(slots=True)
class SnapReport:
    snapped_pairs: list[dict[str, Any]] = field(default_factory=list)
    clusters: list[dict[str, Any]] = field(default_factory=list)
    moved_distance_stats: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SplitEvent:
    road_id: str
    other_road_id: str
    segment_index: int
    point: Coordinate
    t: float
    relation: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["point"] = list(self.point)
        return payload


@dataclass(slots=True)
class DuplicateGroup:
    kept_road_id: str
    removed_road_ids: list[str]
    direction: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MergeEvent:
    merged_road_id: str
    source_road_ids: list[str]
    via_node_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DanglingEvent:
    road_id: str
    mode: DanglingMode
    action: str
    length_m: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TopologyRepairResult:
    nodes: list[RoadNode]
    roads: list[RoadEdge]
    before: TopologyReport
    after: TopologyReport
    operations: dict[str, Any]
    debug_layers: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operations": self.operations,
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "nodes": [_node_to_dict(node) for node in self.nodes],
            "roads": [_road_to_dict(road) for road in self.roads],
            "fixed_roads": feature_collection(road.to_geojson_feature() for road in self.roads),
            "topology_report": self.after.to_dict(),
            "debug_layers": self.debug_layers,
        }


def repair_topology(
    nodes: list[RoadNode],
    roads: list[RoadEdge],
    snap_tolerance_m: float = 1.0,
    split_intersections: bool = True,
    merge_collinear: bool = False,
    dangling_mode: DanglingMode = "mark_only",
    dangling_length_threshold_m: float = 10.0,
    respect_layers: bool = True,
    preserve_metadata: bool = True,
    return_debug_layers: bool = True,
    snap_representative: Literal["centroid", "first"] = "centroid",
) -> TopologyRepairResult:
    before = validate_topology(nodes, roads)
    original_roads = [_copy_road(road) for road in roads]

    snapped_nodes, snapped_roads, snap_report = _snap_close_nodes_v2(
        nodes,
        roads,
        tolerance_m=snap_tolerance_m,
        respect_layers=respect_layers,
        representative=snap_representative,
        preserve_metadata=preserve_metadata,
    )

    if split_intersections:
        split_roads, split_events = _split_roads_at_intersections_v2(
            snapped_roads,
            respect_layers=respect_layers,
            preserve_metadata=preserve_metadata,
        )
    else:
        split_roads = snapped_roads
        split_events = []

    deduped_roads, duplicate_groups = _remove_duplicate_edges_v2(split_roads, preserve_metadata=preserve_metadata)

    if merge_collinear:
        merged_roads, merged_events = _merge_collinear_roads(deduped_roads, preserve_metadata=preserve_metadata)
    else:
        merged_roads = deduped_roads
        merged_events = []

    dangling_roads, dangling_events = _handle_dangling_edges(
        merged_roads,
        mode=dangling_mode,
        length_threshold_m=dangling_length_threshold_m,
        preserve_metadata=preserve_metadata,
    )

    repaired_nodes = _nodes_from_roads(dangling_roads, snapped_nodes)
    after = validate_topology(repaired_nodes, dangling_roads)

    operations: dict[str, Any] = {
        "snapped_nodes": len(snap_report.snapped_pairs),
        "snap_report": snap_report.to_dict(),
        "split_edges_added": max(0, len(split_roads) - len(snapped_roads)),
        "split_events": [event.to_dict() for event in split_events],
        "duplicate_edges_removed": sum(len(group.removed_road_ids) for group in duplicate_groups),
        "duplicate_groups": [group.to_dict() for group in duplicate_groups],
        "merged_collinear_roads": len(merged_events),
        "merged_events": [event.to_dict() for event in merged_events],
        "dangling_edges": [event.to_dict() for event in dangling_events],
        "dangling_edges_removed": sum(1 for event in dangling_events if event.action == "removed"),
    }

    debug_layers = (
        _build_debug_layers(
            original_roads=original_roads,
            snapped_nodes=snapped_nodes,
            split_events=split_events,
            duplicate_groups=duplicate_groups,
            merged_events=merged_events,
            dangling_events=dangling_events,
            repaired_roads=dangling_roads,
        )
        if return_debug_layers
        else {}
    )
    return TopologyRepairResult(repaired_nodes, dangling_roads, before, after, operations, debug_layers)


def _snap_close_nodes_v2(
    nodes: list[RoadNode],
    roads: list[RoadEdge],
    tolerance_m: float,
    respect_layers: bool,
    representative: Literal["centroid", "first"],
    preserve_metadata: bool,
) -> tuple[list[RoadNode], list[RoadEdge], SnapReport]:
    if not nodes:
        return [], list(roads), SnapReport()

    union_find = _UnionFind(node.id for node in nodes)
    node_layers = _node_layer_contexts(roads)
    connected_pairs = {frozenset((road.from_node, road.to_node)) for road in roads if road.from_node != road.to_node}

    for index, first in enumerate(nodes):
        for second in nodes[index + 1 :]:
            if frozenset((first.id, second.id)) in connected_pairs:
                continue
            if respect_layers and not _node_layers_compatible(node_layers.get(first.id, set()), node_layers.get(second.id, set())):
                continue
            if haversine_distance(first.coordinate, second.coordinate) <= tolerance_m:
                union_find.union(first.id, second.id)

    grouped: dict[str, list[RoadNode]] = defaultdict(list)
    for node in nodes:
        grouped[union_find.find(node.id)].append(node)

    mapping: dict[str, str] = {}
    snapped_nodes: list[RoadNode] = []
    moved_distances: list[float] = []
    snapped_pairs: list[dict[str, Any]] = []
    clusters: list[dict[str, Any]] = []
    coord_by_representative: dict[str, Coordinate] = {}

    for root, cluster in grouped.items():
        rep_id = root
        if representative == "first":
            rep_coord = cluster[0].coordinate
            rep_id = cluster[0].id
        else:
            rep_coord = (
                sum(node.lon for node in cluster) / len(cluster),
                sum(node.lat for node in cluster) / len(cluster),
            )
        snapped_nodes.append(RoadNode(rep_id, rep_coord[0], rep_coord[1]))
        coord_by_representative[rep_id] = rep_coord
        clusters.append(
            {
                "representative": rep_id,
                "node_ids": [node.id for node in cluster],
                "coordinate": list(rep_coord),
                "size": len(cluster),
            }
        )
        for node in cluster:
            mapping[node.id] = rep_id
            moved = haversine_distance(node.coordinate, rep_coord)
            moved_distances.append(moved)
            if node.id != rep_id or moved > 1e-9:
                snapped_pairs.append(
                    {
                        "source_node": node.id,
                        "target_node": rep_id,
                        "source_coordinate": list(node.coordinate),
                        "target_coordinate": list(rep_coord),
                        "distance_m": moved,
                    }
                )

    snapped_roads: list[RoadEdge] = []
    for road in roads:
        from_node = mapping.get(road.from_node, road.from_node)
        to_node = mapping.get(road.to_node, road.to_node)
        geometry = list(road.geometry)
        if from_node in coord_by_representative and geometry:
            geometry[0] = coord_by_representative[from_node]
        if to_node in coord_by_representative and geometry:
            geometry[-1] = coord_by_representative[to_node]
        snapped_roads.append(
            _with_history(
                road,
                preserve_metadata,
                "snap_close_nodes",
                from_node=from_node,
                to_node=to_node,
                geometry=geometry,
                length=polyline_length(geometry),
            )
        )

    report = SnapReport(
        snapped_pairs=snapped_pairs,
        clusters=clusters,
        moved_distance_stats=_distance_stats(moved_distances),
    )
    return snapped_nodes, snapped_roads, report


def _split_roads_at_intersections_v2(
    roads: list[RoadEdge],
    respect_layers: bool,
    preserve_metadata: bool,
) -> tuple[list[RoadEdge], list[SplitEvent]]:
    split_events_by_road: dict[str, list[SplitEvent]] = {road.id: [] for road in roads}

    for first_index, first in enumerate(roads):
        for second in roads[first_index + 1 :]:
            if _allow_crossing(first) or _allow_crossing(second):
                continue
            if respect_layers and not _roads_same_planar_layer(first, second):
                continue
            for a_index, (a1, a2) in enumerate(zip(first.geometry, first.geometry[1:], strict=False)):
                for b_index, (b1, b2) in enumerate(zip(second.geometry, second.geometry[1:], strict=False)):
                    intersection = segment_intersection(a1, a2, b1, b2)
                    if intersection.kind != "point" or intersection.point is None:
                        continue
                    if intersection.relation == "endpoint_touch":
                        continue
                    point = intersection.point
                    if not _point_is_segment_endpoint(point, a1, a2):
                        split_events_by_road[first.id].append(
                            SplitEvent(first.id, second.id, a_index, point, _segment_t(point, a1, a2), intersection.relation)
                        )
                    if not _point_is_segment_endpoint(point, b1, b2):
                        split_events_by_road[second.id].append(
                            SplitEvent(second.id, first.id, b_index, point, _segment_t(point, b1, b2), intersection.relation)
                        )

    split_events = [_dedupe_split_events(events) for events in split_events_by_road.values()]
    flat_events = [event for events in split_events for event in events]

    result: list[RoadEdge] = []
    for road in roads:
        events = _dedupe_split_events(split_events_by_road[road.id])
        if not events:
            result.append(road)
            continue
        chain = _insert_split_events(road.geometry, events)
        for index, (start, end) in enumerate(zip(chain, chain[1:], strict=False)):
            if same_point(start, end):
                continue
            geometry = [start, end]
            result.append(
                _with_history(
                    road,
                    preserve_metadata,
                    "split_intersection",
                    id=f"{road.id}_split_{index}",
                    from_node=_node_id(start),
                    to_node=_node_id(end),
                    geometry=geometry,
                    length=polyline_length(geometry),
                    metadata_extra={"source_edge": road.id, "original_ids": _original_ids(road)},
                )
            )
    return result, flat_events


def _remove_duplicate_edges_v2(
    roads: list[RoadEdge],
    preserve_metadata: bool,
) -> tuple[list[RoadEdge], list[DuplicateGroup]]:
    groups: dict[tuple[tuple[tuple[float, float], ...], tuple[Any, ...]], list[tuple[RoadEdge, str]]] = defaultdict(list)
    for road in roads:
        forward = tuple(_rounded(point) for point in road.geometry)
        reverse = tuple(reversed(forward))
        direction = "same_direction" if forward <= reverse else "reverse_direction"
        geometry_key = min(forward, reverse)
        groups[(geometry_key, _semantic_duplicate_key(road))].append((road, direction))

    kept: list[RoadEdge] = []
    duplicate_groups: list[DuplicateGroup] = []
    for grouped_roads in groups.values():
        if len(grouped_roads) == 1:
            kept.append(grouped_roads[0][0])
            continue
        if _is_legal_reverse_oneway_pair([road for road, _direction in grouped_roads]):
            kept.extend(road for road, _direction in grouped_roads)
            continue
        winner = max((road for road, _direction in grouped_roads), key=_metadata_score)
        removed = [road for road, _direction in grouped_roads if road.id != winner.id]
        kept.append(
            _with_history(
                winner,
                preserve_metadata,
                "remove_duplicate_edges_keep",
                metadata_extra={"duplicate_removed_ids": [road.id for road in removed]},
            )
        )
        duplicate_groups.append(
            DuplicateGroup(
                kept_road_id=winner.id,
                removed_road_ids=[road.id for road in removed],
                direction="mixed" if len({direction for _road, direction in grouped_roads}) > 1 else grouped_roads[0][1],
                reason="same geometry and compatible semantics",
            )
        )
    return kept, duplicate_groups


def _merge_collinear_roads(
    roads: list[RoadEdge],
    preserve_metadata: bool,
    angle_threshold_degrees: float = 5.0,
) -> tuple[list[RoadEdge], list[MergeEvent]]:
    current = list(roads)
    events: list[MergeEvent] = []
    changed = True
    while changed:
        changed = False
        degree = _node_degree(current)
        by_node = _roads_by_endpoint(current)
        consumed: set[str] = set()
        merged: list[RoadEdge] = []
        for road in current:
            if road.id in consumed:
                continue
            candidate_merge: tuple[RoadEdge, RoadEdge, str, list[Coordinate]] | None = None
            for node_id in (road.from_node, road.to_node):
                if degree[node_id] != 2:
                    continue
                partners = [candidate for candidate in by_node[node_id] if candidate.id != road.id and candidate.id not in consumed]
                if len(partners) != 1:
                    continue
                partner = partners[0]
                oriented = _oriented_merge_geometry(road, partner, node_id)
                if oriented is None or not _roads_merge_compatible(road, partner):
                    continue
                if _turn_angle(oriented) <= angle_threshold_degrees:
                    candidate_merge = (road, partner, node_id, oriented)
                    break
            if candidate_merge is None:
                merged.append(road)
                continue
            first, second, node_id, geometry = candidate_merge
            merged_id = f"{first.id}_merge_{second.id}"
            merged_road = _with_history(
                first,
                preserve_metadata,
                "merge_collinear_roads",
                id=merged_id,
                from_node=_node_id(geometry[0]),
                to_node=_node_id(geometry[-1]),
                geometry=geometry,
                length=polyline_length(geometry),
                metadata_extra={"source_edge": first.id, "original_ids": sorted(set(_original_ids(first) + _original_ids(second)))},
            )
            consumed.update({first.id, second.id})
            merged.append(merged_road)
            events.append(MergeEvent(merged_id, [first.id, second.id], node_id))
            changed = True
        current = merged + [road for road in current if road.id not in consumed and road.id not in {item.id for item in merged}]
    return current, events


def _handle_dangling_edges(
    roads: list[RoadEdge],
    mode: DanglingMode,
    length_threshold_m: float,
    preserve_metadata: bool,
) -> tuple[list[RoadEdge], list[DanglingEvent]]:
    degree = _node_degree(roads)
    result: list[RoadEdge] = []
    events: list[DanglingEvent] = []
    for road in roads:
        is_dangling = degree[road.from_node] <= 1 or degree[road.to_node] <= 1
        if not is_dangling:
            result.append(road)
            continue
        action = "marked"
        if mode == "remove_all" or (mode == "remove_short" and road.length <= length_threshold_m):
            action = "removed"
        events.append(DanglingEvent(road.id, mode, action, road.length))
        if action == "removed":
            continue
        result.append(
            _with_history(
                road,
                preserve_metadata,
                "mark_dangling_edge",
                metadata_extra={"dangling": True, "dangling_mode": mode},
            )
        )
    return result, events


def _insert_split_events(polyline: list[Coordinate], events: list[SplitEvent]) -> list[Coordinate]:
    events_by_segment: dict[int, list[SplitEvent]] = defaultdict(list)
    for event in events:
        events_by_segment[event.segment_index].append(event)
    for segment_events in events_by_segment.values():
        segment_events.sort(key=lambda event: event.t)

    chain: list[Coordinate] = []
    for segment_index, (start, end) in enumerate(zip(polyline, polyline[1:], strict=False)):
        if not chain:
            chain.append(start)
        for event in events_by_segment.get(segment_index, []):
            if not same_point(event.point, chain[-1]):
                chain.append(event.point)
        if not same_point(end, chain[-1]):
            chain.append(end)
    return chain


def _dedupe_split_events(events: list[SplitEvent]) -> list[SplitEvent]:
    deduped: list[SplitEvent] = []
    for event in sorted(events, key=lambda item: (item.segment_index, item.t, item.other_road_id)):
        if not any(existing.segment_index == event.segment_index and same_point(existing.point, event.point) for existing in deduped):
            deduped.append(event)
    return deduped


def _nodes_from_roads(roads: list[RoadEdge], fallback_nodes: list[RoadNode]) -> list[RoadNode]:
    nodes: dict[str, RoadNode] = {node.id: node for node in fallback_nodes}
    for road in roads:
        if not road.geometry:
            continue
        start = road.geometry[0]
        end = road.geometry[-1]
        nodes[road.from_node] = RoadNode(road.from_node, start[0], start[1])
        nodes[road.to_node] = RoadNode(road.to_node, end[0], end[1])
    return list(nodes.values())


def _build_debug_layers(
    original_roads: list[RoadEdge],
    snapped_nodes: list[RoadNode],
    split_events: list[SplitEvent],
    duplicate_groups: list[DuplicateGroup],
    merged_events: list[MergeEvent],
    dangling_events: list[DanglingEvent],
    repaired_roads: list[RoadEdge],
) -> dict[str, Any]:
    duplicate_ids = {road_id for group in duplicate_groups for road_id in group.removed_road_ids}
    merged_ids = {road_id for event in merged_events for road_id in event.source_road_ids}
    dangling_ids = {event.road_id for event in dangling_events}
    repaired_by_id = {road.id: road for road in repaired_roads}
    original_by_id = {road.id: road for road in original_roads}
    return {
        "original_roads": feature_collection(_road_feature(road, "original_roads") for road in original_roads),
        "snapped_nodes": feature_collection(_node_feature(node, "snapped_nodes") for node in snapped_nodes),
        "split_points": feature_collection(_split_event_feature(event) for event in split_events),
        "duplicate_edges": feature_collection(
            _road_feature(original_by_id[road_id], "duplicate_edges")
            for road_id in duplicate_ids
            if road_id in original_by_id
        ),
        "merged_roads": feature_collection(
            _road_feature(original_by_id[road_id], "merged_roads")
            for road_id in merged_ids
            if road_id in original_by_id
        ),
        "dangling_edges": feature_collection(
            _road_feature(repaired_by_id[road_id], "dangling_edges")
            for road_id in dangling_ids
            if road_id in repaired_by_id
        ),
        "repaired_roads": feature_collection(_road_feature(road, "repaired_roads") for road in repaired_roads),
    }


def _with_history(
    road: RoadEdge,
    preserve_metadata: bool,
    operation: str,
    metadata_extra: dict[str, Any] | None = None,
    **changes: Any,
) -> RoadEdge:
    metadata = dict(road.metadata or {}) if preserve_metadata else {}
    metadata.update(metadata_extra or {})
    metadata.setdefault("source_edge", road.metadata.get("source_edge", road.id) if road.metadata else road.id)
    metadata.setdefault("original_ids", _original_ids(road))
    history = list(metadata.get("repair_history") or [])
    history.append(operation)
    metadata["repair_history"] = history
    changes.setdefault("metadata", metadata)
    return _copy_road(road, **changes)


def _copy_road(road: RoadEdge, **changes: Any) -> RoadEdge:
    values = {
        "id": road.id,
        "from_node": road.from_node,
        "to_node": road.to_node,
        "geometry": list(road.geometry),
        "length": road.length,
        "speed_limit": road.speed_limit,
        "road_type": road.road_type,
        "oneway": road.oneway,
        "direction": road.direction,
        "road_class": road.road_class,
        "lane_count": road.lane_count,
        "turn_restrictions": list(road.turn_restrictions or []),
        "metadata": dict(road.metadata or {}),
    }
    values.update(changes)
    return RoadEdge(**values)


def _node_layers_compatible(first: set[tuple[Any, bool, bool]], second: set[tuple[Any, bool, bool]]) -> bool:
    if not first or not second:
        return True
    return bool(first & second)


def _node_layer_contexts(roads: list[RoadEdge]) -> dict[str, set[tuple[Any, bool, bool]]]:
    contexts: dict[str, set[tuple[Any, bool, bool]]] = defaultdict(set)
    for road in roads:
        key = _road_layer_key(road)
        contexts[road.from_node].add(key)
        contexts[road.to_node].add(key)
    return contexts


def _roads_same_planar_layer(first: RoadEdge, second: RoadEdge) -> bool:
    return _road_layer_key(first) == _road_layer_key(second)


def _road_layer_key(road: RoadEdge) -> tuple[Any, bool, bool]:
    metadata = road.metadata or {}
    layer = metadata.get("layer", 0)
    bridge = bool(metadata.get("bridge", False))
    tunnel = bool(metadata.get("tunnel", False))
    return layer, bridge, tunnel


def _allow_crossing(road: RoadEdge) -> bool:
    return bool((road.metadata or {}).get("allow_crossing", False))


def _point_is_segment_endpoint(point: Coordinate, start: Coordinate, end: Coordinate) -> bool:
    return same_point(point, start) or same_point(point, end)


def _segment_t(point: Coordinate, start: Coordinate, end: Coordinate) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    denominator = dx * dx + dy * dy
    if denominator <= 1e-24:
        return 0.0
    return ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / denominator


def _semantic_duplicate_key(road: RoadEdge) -> tuple[Any, ...]:
    layer, bridge, tunnel = _road_layer_key(road)
    return (road.road_class, road.speed_limit, layer, bridge, tunnel)


def _is_legal_reverse_oneway_pair(roads: list[RoadEdge]) -> bool:
    if len(roads) != 2:
        return False
    first, second = roads
    first_geom = [_rounded(point) for point in first.geometry]
    second_geom = [_rounded(point) for point in second.geometry]
    return first.oneway and second.oneway and first_geom == list(reversed(second_geom))


def _metadata_score(road: RoadEdge) -> int:
    metadata = road.metadata or {}
    return len(metadata) + sum(1 for value in metadata.values() if value not in (None, "", [], {}))


def _roads_merge_compatible(first: RoadEdge, second: RoadEdge) -> bool:
    return (
        first.road_class == second.road_class
        and first.oneway == second.oneway
        and first.direction == second.direction
        and abs(first.speed_limit - second.speed_limit) <= 1e-6
        and _road_layer_key(first) == _road_layer_key(second)
    )


def _oriented_merge_geometry(first: RoadEdge, second: RoadEdge, via_node_id: str) -> list[Coordinate] | None:
    first_geometry = _geometry_ending_at(first, via_node_id)
    second_geometry = _geometry_starting_at(second, via_node_id)
    if first_geometry and second_geometry:
        return first_geometry + second_geometry[1:]
    second_geometry = _geometry_ending_at(second, via_node_id)
    first_geometry = _geometry_starting_at(first, via_node_id)
    if second_geometry and first_geometry:
        return second_geometry + first_geometry[1:]
    return None


def _geometry_ending_at(road: RoadEdge, node_id: str) -> list[Coordinate] | None:
    if road.to_node == node_id:
        return list(road.geometry)
    if not road.oneway and road.from_node == node_id:
        return list(reversed(road.geometry))
    return None


def _geometry_starting_at(road: RoadEdge, node_id: str) -> list[Coordinate] | None:
    if road.from_node == node_id:
        return list(road.geometry)
    if not road.oneway and road.to_node == node_id:
        return list(reversed(road.geometry))
    return None


def _turn_angle(geometry: list[Coordinate]) -> float:
    if len(geometry) < 3:
        return 0.0
    heading_in = bearing(geometry[-3], geometry[-2])
    heading_out = bearing(geometry[-2], geometry[-1])
    return abs((heading_out - heading_in + 180.0) % 360.0 - 180.0)


def _node_degree(roads: list[RoadEdge]) -> dict[str, int]:
    degree: dict[str, int] = defaultdict(int)
    for road in roads:
        degree[road.from_node] += 1
        degree[road.to_node] += 1
    return degree


def _roads_by_endpoint(roads: list[RoadEdge]) -> dict[str, list[RoadEdge]]:
    by_node: dict[str, list[RoadEdge]] = defaultdict(list)
    for road in roads:
        by_node[road.from_node].append(road)
        by_node[road.to_node].append(road)
    return by_node


def _original_ids(road: RoadEdge) -> list[str]:
    metadata = road.metadata or {}
    original_ids = metadata.get("original_ids")
    if isinstance(original_ids, list):
        return [str(value) for value in original_ids]
    return [road.id]


def _distance_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0.0, "max_m": 0.0, "mean_m": 0.0, "total_m": 0.0}
    return {
        "count": float(len(values)),
        "max_m": max(values),
        "mean_m": sum(values) / len(values),
        "total_m": sum(values),
    }


def _road_feature(road: RoadEdge, layer: str) -> dict[str, Any]:
    feature = road.to_geojson_feature()
    feature["properties"]["layer"] = layer
    return feature


def _node_feature(node: RoadNode, layer: str) -> dict[str, Any]:
    return {
        "type": "Feature",
        "id": node.id,
        "properties": {"id": node.id, "layer": layer},
        "geometry": {"type": "Point", "coordinates": [node.lon, node.lat]},
    }


def _split_event_feature(event: SplitEvent) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {
            "layer": "split_points",
            "road_id": event.road_id,
            "other_road_id": event.other_road_id,
            "relation": event.relation,
            "t": event.t,
        },
        "geometry": {"type": "Point", "coordinates": list(event.point)},
    }


def _road_to_dict(road: RoadEdge) -> dict[str, Any]:
    return {
        "id": road.id,
        "from_node": road.from_node,
        "to_node": road.to_node,
        "geometry": [list(point) for point in road.geometry],
        "length": road.length,
        "speed_limit": road.speed_limit,
        "road_type": road.road_type,
        "oneway": road.oneway,
        "direction": road.direction,
        "road_class": road.road_class,
        "lane_count": road.lane_count,
        "turn_restrictions": road.turn_restrictions or [],
        "metadata": road.metadata or {},
    }


def _node_to_dict(node: RoadNode) -> dict[str, Any]:
    return {"id": node.id, "lon": node.lon, "lat": node.lat}


def _node_id(coord: Coordinate) -> str:
    return f"node_{coord[0]:.7f}_{coord[1]:.7f}".replace(".", "_").replace("-", "m")


def _rounded(point: Coordinate, digits: int = 7) -> tuple[float, float]:
    return (round(point[0], digits), round(point[1], digits))


class _UnionFind:
    def __init__(self, items: Iterable[str]) -> None:
        item_list = list(items)
        self.parent = {item: item for item in item_list}
        self.rank = {item: 0 for item in item_list}

    def find(self, item: str) -> str:
        parent = self.parent[item]
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, first: str, second: str) -> None:
        root_first = self.find(first)
        root_second = self.find(second)
        if root_first == root_second:
            return
        if self.rank[root_first] < self.rank[root_second]:
            self.parent[root_first] = root_second
        elif self.rank[root_first] > self.rank[root_second]:
            self.parent[root_second] = root_first
        else:
            self.parent[root_second] = root_first
            self.rank[root_first] += 1
