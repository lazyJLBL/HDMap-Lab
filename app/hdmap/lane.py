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


@dataclass(slots=True)
class Lane:
    id: str
    centerline: list[Coordinate]
    left_boundary: str | None = None
    right_boundary: str | None = None
    speed_limit: float = 40.0
    turn_type: str = "through"
    predecessor_ids: list[str] = field(default_factory=list)
    successor_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LaneConnector:
    id: str
    from_lane: str
    to_lane: str
    geometry: list[Coordinate]


@dataclass(slots=True)
class StopLine:
    id: str
    geometry: list[Coordinate]
    lane_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Crosswalk:
    id: str
    polygon: list[list[Coordinate]]


@dataclass(slots=True)
class TrafficLight:
    id: str
    coordinate: Coordinate
    controlled_lanes: list[str] = field(default_factory=list)
