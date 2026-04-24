from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.point import Coordinate


@dataclass(slots=True)
class Polygon:
    id: str
    coordinates: list[list[Coordinate]]

    @property
    def exterior(self) -> list[Coordinate]:
        return self.coordinates[0] if self.coordinates else []

    def to_geojson_feature(self, properties: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "type": "Feature",
            "id": self.id,
            "properties": {"id": self.id, **(properties or {})},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[lon, lat] for lon, lat in ring] for ring in self.coordinates
                ],
            },
        }

