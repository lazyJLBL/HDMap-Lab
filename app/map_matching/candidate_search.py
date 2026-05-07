from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.bbox import bbox_expand_m, bbox_of_coords
from app.core.geometry import angle_difference, bearing, point_to_polyline_distance
from app.index.kdtree import KDTree
from app.index.rtree import RTreeIndex
from app.models import RoadEdge
from app.models.point import Coordinate


@dataclass(slots=True)
class RoadCandidate:
    road: RoadEdge
    distance_m: float
    projected_point: Coordinate
    segment_index: int
    t: float
    road_heading: float
    heading_diff: float | None = None
    road_class: str = "local"
    layer: int = 0
    is_oneway_compatible: bool = True
    score_features: dict[str, Any] = field(default_factory=dict)
    travel_direction: str = "forward"

    @property
    def distance(self) -> float:
        return self.distance_m

    @property
    def projection_point(self) -> Coordinate:
        return self.projected_point

    @property
    def oneway_allowed(self) -> bool:
        return self.is_oneway_compatible

    def to_dict(self) -> dict[str, Any]:
        return {
            "road_id": self.road.id,
            "projected_point": [self.projected_point[0], self.projected_point[1]],
            "projection_point": [self.projected_point[0], self.projected_point[1]],
            "distance_m": self.distance_m,
            "distance": self.distance_m,
            "segment_index": self.segment_index,
            "t": self.t,
            "heading_diff": self.heading_diff,
            "road_class": self.road_class,
            "layer": self.layer,
            "is_oneway_compatible": self.is_oneway_compatible,
            "oneway_allowed": self.is_oneway_compatible,
            "score_features": self.score_features,
            "road_heading": self.road_heading,
            "travel_direction": self.travel_direction,
            "geometry": {
                "type": "LineString",
                "coordinates": [[lon, lat] for lon, lat in self.road.geometry],
            },
        }


class CandidateSearcher:
    def __init__(
        self,
        roads: list[RoadEdge],
        road_rtree: RTreeIndex[str] | None = None,
        road_kdtree: KDTree[str] | None = None,
    ):
        self.roads = {road.id: road for road in roads}
        self.road_rtree = road_rtree or RTreeIndex(road_bbox_items(roads))
        self.road_kdtree = road_kdtree or KDTree(road_centroid_items(roads))

    def nearby_roads(self, point: Coordinate, k: int = 5) -> list[RoadCandidate]:
        return self.search(point, k=k)

    def search(
        self,
        point: Coordinate,
        radius_m: float = 150.0,
        k: int = 5,
        heading: float | None = None,
        heading_tolerance_degrees: float | None = None,
        road_class_filter: set[str] | list[str] | None = None,
        layer_filter: set[int] | list[int] | None = None,
        allow_fallback: bool = True,
    ) -> list[RoadCandidate]:
        if not self.roads:
            return []
        road_classes = set(road_class_filter or [])
        layers = {int(layer) for layer in (layer_filter or [])}
        candidate_ids = set(self.road_rtree.query(bbox_expand_m(point, radius_m)))
        if len(candidate_ids) < k and allow_fallback:
            for fallback_radius in (radius_m * 2, radius_m * 5, radius_m * 10, 5000.0):
                candidate_ids.update(self.road_rtree.query(bbox_expand_m(point, fallback_radius)))
                if len(candidate_ids) >= max(k, 8):
                    break
        candidate_ids.update(self.road_kdtree.nearest(point, max(k * 4, 20)))
        if len(candidate_ids) < k and allow_fallback:
            candidate_ids.update(self.roads.keys())

        candidates: list[RoadCandidate] = []
        for road_id in candidate_ids:
            road = self.roads[road_id]
            road_layer = _road_layer(road)
            if road_classes and road.road_class not in road_classes:
                continue
            if layers and road_layer not in layers:
                continue
            projection = point_to_polyline_distance(point, road.geometry)
            start = road.geometry[projection.segment_index]
            end = road.geometry[min(projection.segment_index + 1, len(road.geometry) - 1)]
            road_heading = bearing(start, end)
            heading_diff = _candidate_heading_diff(road, road_heading, heading)
            if heading_tolerance_degrees is not None and heading_diff is not None and heading_diff > heading_tolerance_degrees:
                continue
            compatible = _oneway_compatible(road, heading, road_heading)
            candidates.append(
                RoadCandidate(
                    road=road,
                    distance_m=projection.distance_m,
                    projected_point=projection.projected_point,
                    segment_index=projection.segment_index,
                    t=projection.t,
                    road_heading=road_heading,
                    heading_diff=heading_diff,
                    road_class=road.road_class,
                    layer=road_layer,
                    is_oneway_compatible=compatible,
                    score_features={
                        "distance_m": projection.distance_m,
                        "heading_diff": heading_diff,
                        "road_class": road.road_class,
                        "layer": road_layer,
                        "oneway": road.oneway,
                    },
                )
            )
        candidates.sort(key=lambda candidate: (candidate.distance_m, candidate.heading_diff or 0.0))
        return candidates[:k]

    def candidate_debug_layers(self, point: Coordinate, candidates: list[RoadCandidate]) -> dict[str, Any]:
        return {
            "candidate_roads": {
                "type": "FeatureCollection",
                "features": [_candidate_road_feature(candidate) for candidate in candidates],
            },
            "candidate_projections": {
                "type": "FeatureCollection",
                "features": [_candidate_point_feature(point, candidate) for candidate in candidates],
            },
        }


def candidate_search_summary(point: Coordinate, candidates: list[RoadCandidate]) -> dict[str, Any]:
    return {
        "point": [point[0], point[1]],
        "candidate_count": len(candidates),
        "candidates": [candidate.to_dict() for candidate in candidates],
    }


def road_bbox_items(roads: list[RoadEdge]) -> list[tuple[tuple[float, float, float, float], str]]:
    return [(bbox_of_coords(road.geometry), road.id) for road in roads if road.geometry]


def road_centroid_items(roads: list[RoadEdge]) -> list[tuple[Coordinate, str]]:
    items: list[tuple[Coordinate, str]] = []
    for road in roads:
        if not road.geometry:
            continue
        bbox = bbox_of_coords(road.geometry)
        items.append((((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0), road.id))
    return items


def _candidate_heading_diff(road: RoadEdge, road_heading: float, gps_heading: float | None) -> float | None:
    if gps_heading is None:
        return None
    if road.oneway:
        return angle_difference(gps_heading, road_heading)
    return min(angle_difference(gps_heading, road_heading), angle_difference(gps_heading, (road_heading + 180.0) % 360.0))


def _oneway_compatible(road: RoadEdge, gps_heading: float | None, road_heading: float) -> bool:
    if not road.oneway or gps_heading is None:
        return True
    return angle_difference(gps_heading, road_heading) <= 90.0


def _road_layer(road: RoadEdge) -> int:
    try:
        return int((road.metadata or {}).get("layer", 0))
    except (TypeError, ValueError):
        return 0


def _candidate_road_feature(candidate: RoadCandidate) -> dict[str, Any]:
    feature = candidate.road.to_geojson_feature()
    feature["properties"].update(
        {
            "layer": "candidate_roads",
            "distance_m": candidate.distance_m,
            "heading_diff": candidate.heading_diff,
            "candidate_score": candidate.distance_m,
        }
    )
    return feature


def _candidate_point_feature(point: Coordinate, candidate: RoadCandidate) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {
            "layer": "candidate_projections",
            "road_id": candidate.road.id,
            "distance_m": candidate.distance_m,
        },
        "geometry": {"type": "Point", "coordinates": [candidate.projected_point[0], candidate.projected_point[1]]},
    }
