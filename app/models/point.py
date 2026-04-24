from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Coordinate = tuple[float, float]


@dataclass(slots=True)
class Point:
    id: str
    lon: float
    lat: float

    @property
    def coordinate(self) -> Coordinate:
        return (self.lon, self.lat)

    def to_geojson_feature(self) -> dict[str, Any]:
        return {
            "type": "Feature",
            "id": self.id,
            "properties": {"id": self.id},
            "geometry": {"type": "Point", "coordinates": [self.lon, self.lat]},
        }


@dataclass(slots=True)
class POI(Point):
    name: str = ""
    properties: dict[str, Any] = field(default_factory=dict)

    def to_geojson_feature(self) -> dict[str, Any]:
        properties = {"id": self.id, "name": self.name, **self.properties}
        return {
            "type": "Feature",
            "id": self.id,
            "properties": properties,
            "geometry": {"type": "Point", "coordinates": [self.lon, self.lat]},
        }

