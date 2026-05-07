from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.point import Coordinate


@dataclass(slots=True)
class LaneBoundary:
    id: str
    geometry: list[Coordinate]
    boundary_type: str = "unknown"
    color: str = "unknown"
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(init=False, slots=True)
class Lane:
    id: str
    centerline: list[Coordinate]
    left_boundary_id: str | None
    right_boundary_id: str | None
    predecessor_lane_ids: list[str]
    successor_lane_ids: list[str]
    left_neighbor_lane_id: str | None
    right_neighbor_lane_id: str | None
    lane_type: str
    turn_type: str
    speed_limit: float
    road_id: str | None
    section_id: str | None
    junction_id: str | None
    metadata: dict[str, Any]

    def __init__(
        self,
        id: str,
        centerline: list[Coordinate],
        left_boundary_id: str | None = None,
        right_boundary_id: str | None = None,
        predecessor_lane_ids: list[str] | None = None,
        successor_lane_ids: list[str] | None = None,
        left_neighbor_lane_id: str | None = None,
        right_neighbor_lane_id: str | None = None,
        lane_type: str = "driving",
        turn_type: str = "through",
        speed_limit: float = 40.0,
        road_id: str | None = None,
        section_id: str | None = None,
        junction_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        left_boundary: str | None = None,
        right_boundary: str | None = None,
        predecessor_ids: list[str] | None = None,
        successor_ids: list[str] | None = None,
    ) -> None:
        self.id = id
        self.centerline = centerline
        self.left_boundary_id = left_boundary_id if left_boundary_id is not None else left_boundary
        self.right_boundary_id = right_boundary_id if right_boundary_id is not None else right_boundary
        self.predecessor_lane_ids = predecessor_lane_ids if predecessor_lane_ids is not None else list(predecessor_ids or [])
        self.successor_lane_ids = successor_lane_ids if successor_lane_ids is not None else list(successor_ids or [])
        self.left_neighbor_lane_id = left_neighbor_lane_id
        self.right_neighbor_lane_id = right_neighbor_lane_id
        self.lane_type = lane_type
        self.turn_type = turn_type
        self.speed_limit = speed_limit
        self.road_id = road_id
        self.section_id = section_id
        self.junction_id = junction_id
        self.metadata = metadata or {}

    @property
    def left_boundary(self) -> str | None:
        return self.left_boundary_id

    @left_boundary.setter
    def left_boundary(self, value: str | None) -> None:
        self.left_boundary_id = value

    @property
    def right_boundary(self) -> str | None:
        return self.right_boundary_id

    @right_boundary.setter
    def right_boundary(self, value: str | None) -> None:
        self.right_boundary_id = value

    @property
    def predecessor_ids(self) -> list[str]:
        return self.predecessor_lane_ids

    @predecessor_ids.setter
    def predecessor_ids(self, value: list[str]) -> None:
        self.predecessor_lane_ids = value

    @property
    def successor_ids(self) -> list[str]:
        return self.successor_lane_ids

    @successor_ids.setter
    def successor_ids(self, value: list[str]) -> None:
        self.successor_lane_ids = value

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "centerline": [[lon, lat] for lon, lat in self.centerline],
            "left_boundary_id": self.left_boundary_id,
            "right_boundary_id": self.right_boundary_id,
            "predecessor_lane_ids": self.predecessor_lane_ids,
            "successor_lane_ids": self.successor_lane_ids,
            "left_neighbor_lane_id": self.left_neighbor_lane_id,
            "right_neighbor_lane_id": self.right_neighbor_lane_id,
            "lane_type": self.lane_type,
            "turn_type": self.turn_type,
            "speed_limit": self.speed_limit,
            "road_id": self.road_id,
            "section_id": self.section_id,
            "junction_id": self.junction_id,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class LaneConnector:
    id: str
    from_lane_id: str
    to_lane_id: str
    geometry: list[Coordinate]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def from_lane(self) -> str:
        return self.from_lane_id

    @property
    def to_lane(self) -> str:
        return self.to_lane_id


@dataclass(slots=True)
class StopLine:
    id: str
    geometry: list[Coordinate]
    lane_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Crosswalk:
    id: str
    polygon: list[list[Coordinate]]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TrafficLight:
    id: str
    coordinate: Coordinate
    controlled_lanes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TrafficSign:
    id: str
    coordinate: Coordinate
    sign_type: str = "unknown"
    controlled_lanes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LaneNode:
    id: str
    coordinate: Coordinate
    lane_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LaneRelation:
    from_lane_id: str
    to_lane_id: str
    relation_type: str
    cost: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LaneGraph:
    lanes: dict[str, Lane]
    boundaries: dict[str, LaneBoundary] = field(default_factory=dict)
    successors: dict[str, list[str]] = field(default_factory=dict)
    predecessors: dict[str, list[str]] = field(default_factory=dict)
    relations: list[LaneRelation] = field(default_factory=list)
