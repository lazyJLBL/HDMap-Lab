from __future__ import annotations

from dataclasses import dataclass, field

from app.geometry_kernel.polyline import bearing
from app.index.kdtree import KDTree
from app.models import RoadEdge, RoadNode
from app.models.point import Coordinate


@dataclass(slots=True)
class GraphArc:
    edge_id: str
    from_node: str
    to_node: str
    length: float
    travel_time: float
    geometry: list[Coordinate]
    road_class: str = "local"
    speed_limit: float = 40.0
    direction: str = "both"
    lane_count: int = 1
    heading: float = 0.0


@dataclass
class RoadGraph:
    nodes: dict[str, RoadNode]
    roads: dict[str, RoadEdge]
    adjacency: dict[str, list[GraphArc]] = field(default_factory=dict)
    node_index: KDTree[str] | None = None

    @classmethod
    def build(cls, nodes: list[RoadNode], roads: list[RoadEdge]) -> "RoadGraph":
        node_map = {node.id: node for node in nodes}
        road_map = {road.id: road for road in roads}
        adjacency: dict[str, list[GraphArc]] = {node.id: [] for node in nodes}
        for road in roads:
            adjacency.setdefault(road.from_node, []).append(
                GraphArc(
                    edge_id=road.id,
                    from_node=road.from_node,
                    to_node=road.to_node,
                    length=road.length,
                    travel_time=road.travel_time,
                    geometry=road.geometry,
                    road_class=road.road_class,
                    speed_limit=road.speed_limit,
                    direction=road.direction,
                    lane_count=road.lane_count,
                    heading=bearing(road.geometry[0], road.geometry[-1]),
                )
            )
            if not road.oneway:
                adjacency.setdefault(road.to_node, []).append(
                    GraphArc(
                        edge_id=road.id,
                        from_node=road.to_node,
                        to_node=road.from_node,
                        length=road.length,
                        travel_time=road.travel_time,
                        geometry=list(reversed(road.geometry)),
                        road_class=road.road_class,
                        speed_limit=road.speed_limit,
                        direction="reverse" if road.direction == "forward" else road.direction,
                        lane_count=road.lane_count,
                        heading=bearing(road.geometry[-1], road.geometry[0]),
                    )
                )
        node_index = KDTree((node.coordinate, node.id) for node in nodes)
        return cls(node_map, road_map, adjacency, node_index)

    def nearest_node_id(self, point: Coordinate) -> str | None:
        if self.node_index is None:
            return None
        matches = self.node_index.nearest(point, 1)
        return matches[0] if matches else None

    def arc_weight(self, arc: GraphArc, mode: str) -> float:
        return arc.travel_time if mode == "shortest_time" else arc.length
