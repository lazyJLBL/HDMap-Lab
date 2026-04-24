from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.point import Coordinate


@dataclass(slots=True)
class GeoFence:
    id: str
    name: str
    coordinates: list[list[Coordinate]]

    @property
    def exterior(self) -> list[Coordinate]:
        return self.coordinates[0] if self.coordinates else []

    def to_geojson_feature(self) -> dict[str, Any]:
        return {
            "type": "Feature",
            "id": self.id,
            "properties": {"id": self.id, "name": self.name},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[lon, lat] for lon, lat in ring] for ring in self.coordinates
                ],
            },
        }

