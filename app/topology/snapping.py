from __future__ import annotations

from app.geometry_kernel.polyline import haversine_distance
from app.models import RoadEdge, RoadNode


def snap_close_nodes(
    nodes: list[RoadNode],
    roads: list[RoadEdge],
    tolerance_m: float = 1.0,
) -> tuple[list[RoadNode], list[RoadEdge], dict[str, str]]:
    if not nodes:
        return [], roads, {}
    representatives: list[RoadNode] = []
    mapping: dict[str, str] = {}
    clusters: dict[str, list[RoadNode]] = {}
    for node in nodes:
        matched = next(
            (rep for rep in representatives if haversine_distance(node.coordinate, rep.coordinate) <= tolerance_m),
            None,
        )
        if matched is None:
            representatives.append(node)
            mapping[node.id] = node.id
            clusters[node.id] = [node]
        else:
            mapping[node.id] = matched.id
            clusters[matched.id].append(node)

    snapped_nodes: list[RoadNode] = []
    for rep_id, cluster in clusters.items():
        lon = sum(node.lon for node in cluster) / len(cluster)
        lat = sum(node.lat for node in cluster) / len(cluster)
        snapped_nodes.append(RoadNode(rep_id, lon, lat))
    coord_by_node = {node.id: node.coordinate for node in snapped_nodes}

    snapped_roads: list[RoadEdge] = []
    for road in roads:
        from_node = mapping.get(road.from_node, road.from_node)
        to_node = mapping.get(road.to_node, road.to_node)
        geometry = list(road.geometry)
        if from_node in coord_by_node:
            geometry[0] = coord_by_node[from_node]
        if to_node in coord_by_node:
            geometry[-1] = coord_by_node[to_node]
        snapped_roads.append(_copy_road(road, from_node=from_node, to_node=to_node, geometry=geometry))
    return snapped_nodes, snapped_roads, mapping


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
