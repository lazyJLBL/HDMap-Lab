from __future__ import annotations

from dataclasses import dataclass

from app.core.bbox import bbox_expand_m, bbox_of_coords
from app.core.geometry import bearing, point_to_polyline_distance
from app.index.kdtree import KDTree
from app.index.rtree import RTreeIndex
from app.models import RoadEdge
from app.models.point import Coordinate


@dataclass(slots=True)
class RoadCandidate:
    road: RoadEdge
    distance: float
    projection_point: Coordinate
    segment_index: int
    road_heading: float
    travel_direction: str = "forward"
    oneway_allowed: bool = True

    def to_dict(self) -> dict:
        return {
            "road_id": self.road.id,
            "distance": self.distance,
            "projection_point": [self.projection_point[0], self.projection_point[1]],
            "road_heading": self.road_heading,
            "travel_direction": self.travel_direction,
            "oneway_allowed": self.oneway_allowed,
            "geometry": {
                "type": "LineString",
                "coordinates": [[lon, lat] for lon, lat in self.road.geometry],
            },
        }


class CandidateSearcher:
    def __init__(
        self,
        roads: list[RoadEdge],
        road_rtree: RTreeIndex[str],
        road_kdtree: KDTree[str],
    ):
        self.roads = {road.id: road for road in roads}
        self.road_rtree = road_rtree
        self.road_kdtree = road_kdtree

    def nearby_roads(self, point: Coordinate, k: int = 5) -> list[RoadCandidate]:
        if not self.roads:
            return []
        candidate_ids: set[str] = set()
        for radius in (30, 75, 150, 300, 750, 1500, 5000):
            candidate_ids.update(self.road_rtree.query(bbox_expand_m(point, radius)))
            if len(candidate_ids) >= max(k, 8):
                break
        candidate_ids.update(self.road_kdtree.nearest(point, max(k * 4, 20)))
        if len(candidate_ids) < k:
            candidate_ids.update(self.roads.keys())

        candidates: list[RoadCandidate] = []
        for road_id in candidate_ids:
            road = self.roads[road_id]
            projection = point_to_polyline_distance(point, road.geometry)
            start = road.geometry[projection.segment_index]
            end = road.geometry[min(projection.segment_index + 1, len(road.geometry) - 1)]
            candidates.append(
                RoadCandidate(
                    road=road,
                    distance=projection.distance,
                    projection_point=projection.projection,
                    segment_index=projection.segment_index,
                    road_heading=bearing(start, end),
                    travel_direction="forward",
                    oneway_allowed=True,
                )
            )
        candidates.sort(key=lambda candidate: candidate.distance)
        return candidates[:k]


def road_bbox_items(roads: list[RoadEdge]) -> list[tuple[tuple[float, float, float, float], str]]:
    return [(bbox_of_coords(road.geometry), road.id) for road in roads]


def road_centroid_items(roads: list[RoadEdge]) -> list[tuple[Coordinate, str]]:
    items: list[tuple[Coordinate, str]] = []
    for road in roads:
        bbox = bbox_of_coords(road.geometry)
        items.append((((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0), road.id))
    return items
