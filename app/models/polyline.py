from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.point import Coordinate


@dataclass(slots=True)
class Polyline:
    id: str
    coordinates: list[Coordinate]

    def to_geojson_feature(self, properties: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "type": "Feature",
            "id": self.id,
            "properties": {"id": self.id, **(properties or {})},
            "geometry": {
                "type": "LineString",
                "coordinates": [[lon, lat] for lon, lat in self.coordinates],
            },
        }

