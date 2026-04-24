from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.point import Coordinate


@dataclass(slots=True)
class RoadNode:
    id: str
    lon: float
    lat: float

    @property
    def coordinate(self) -> Coordinate:
        return (self.lon, self.lat)


@dataclass(slots=True)
class RoadEdge:
    id: str
    from_node: str
    to_node: str
    geometry: list[Coordinate]
    length: float
    speed_limit: float = 40.0
    road_type: str = "residential"
    oneway: bool = False

    @property
    def travel_time(self) -> float:
        speed_mps = max(self.speed_limit, 1.0) * 1000.0 / 3600.0
        return self.length / speed_mps

    def to_geojson_feature(self) -> dict[str, Any]:
        return {
            "type": "Feature",
            "id": self.id,
            "properties": {
                "id": self.id,
                "from": self.from_node,
                "to": self.to_node,
                "length": self.length,
                "speed_limit": self.speed_limit,
                "road_type": self.road_type,
                "oneway": self.oneway,
                "travel_time": self.travel_time,
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [[lon, lat] for lon, lat in self.geometry],
            },
        }

