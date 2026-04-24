from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.point import Coordinate


@dataclass(slots=True)
class TrajectoryPoint:
    lon: float
    lat: float
    timestamp: str | None = None

    @property
    def coordinate(self) -> Coordinate:
        return (self.lon, self.lat)


@dataclass(slots=True)
class Trajectory:
    id: str
    points: list[TrajectoryPoint]

    @property
    def coordinates(self) -> list[Coordinate]:
        return [point.coordinate for point in self.points]

    def to_geojson_feature(self) -> dict[str, Any]:
        return {
            "type": "Feature",
            "id": self.id,
            "properties": {
                "id": self.id,
                "timestamps": [point.timestamp for point in self.points],
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [[point.lon, point.lat] for point in self.points],
            },
        }

