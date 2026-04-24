from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any

from app.core.bbox import bbox_of_coords, bbox_of_polygon
from app.core.geojson import feature_collection, normalize_polygon
from app.core.geometry import point_in_polygon, polyline_intersects_polygon
from app.index.kdtree import KDTree
from app.index.rtree import RTreeIndex
from app.map_matching.candidate_search import CandidateSearcher, road_bbox_items, road_centroid_items
from app.models import GeoFence, POI, RoadEdge, RoadNode, Trajectory, TrajectoryPoint
from app.routing.graph_builder import RoadGraph
from app.storage.geojson_loader import (
    load_geofences_collection,
    load_geofences_geojson,
    load_pois_collection,
    load_pois_geojson,
    load_roads_collection,
    load_roads_geojson,
    load_trajectories_collection,
    load_trajectories_geojson,
)
from app.storage.osm_loader import load_osm_file, load_osm_online_bbox, load_osm_online_place
from app.storage.sqlite_store import SQLiteStore

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


class RuntimeState:
    def __init__(self, db_path: str | Path | None = None):
        self.store = SQLiteStore(db_path or DATA_DIR / "hdmap_lab.sqlite")
        self.nodes: list[RoadNode] = []
        self.roads: list[RoadEdge] = []
        self.trajectories: list[Trajectory] = []
        self.geofences: list[GeoFence] = []
        self.pois: list[POI] = []
        self.road_rtree: RTreeIndex[str] = RTreeIndex()
        self.road_kdtree: KDTree[str] = KDTree()
        self.candidate_searcher: CandidateSearcher | None = None
        self.graph: RoadGraph = RoadGraph.build([], [])
        self.lock = Lock()
        if not self.store.has_roads():
            self.load_sample()
        else:
            self.rebuild_indexes()

    def load_sample(self) -> dict[str, int]:
        return self.load_geojson_paths(
            roads_path=DATA_DIR / "roads.geojson",
            trajectories_path=DATA_DIR / "trajectories.geojson",
            geofences_path=DATA_DIR / "geofences.geojson",
            pois_path=DATA_DIR / "pois.geojson",
        )

    def load_geojson_paths(
        self,
        roads_path: str | Path | None = None,
        trajectories_path: str | Path | None = None,
        geofences_path: str | Path | None = None,
        pois_path: str | Path | None = None,
    ) -> dict[str, int]:
        nodes, roads = load_roads_geojson(roads_path or DATA_DIR / "roads.geojson")
        trajectories = (
            load_trajectories_geojson(trajectories_path)
            if trajectories_path
            else load_trajectories_geojson(DATA_DIR / "trajectories.geojson")
        )
        geofences = (
            load_geofences_geojson(geofences_path)
            if geofences_path
            else load_geofences_geojson(DATA_DIR / "geofences.geojson")
        )
        pois = load_pois_geojson(pois_path) if pois_path else load_pois_geojson(DATA_DIR / "pois.geojson")
        return self._replace(nodes, roads, trajectories, geofences, pois)

    def load_geojson_payloads(
        self,
        roads_geojson: dict[str, Any],
        trajectories_geojson: dict[str, Any] | None = None,
        geofences_geojson: dict[str, Any] | None = None,
        pois_geojson: dict[str, Any] | None = None,
    ) -> dict[str, int]:
        nodes, roads = load_roads_collection(roads_geojson)
        trajectories = load_trajectories_collection(trajectories_geojson or {"features": []})
        geofences = load_geofences_collection(geofences_geojson or {"features": []})
        pois = load_pois_collection(pois_geojson or {"features": []})
        return self._replace(nodes, roads, trajectories, geofences, pois)

    def load_osm_path(self, path: str | Path) -> dict[str, int]:
        nodes, roads = load_osm_file(path)
        return self._replace(nodes, roads, self.trajectories, self.geofences, self.pois)

    def load_osm_online(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        place: str | None = None,
    ) -> dict[str, int]:
        if bbox is not None:
            nodes, roads = load_osm_online_bbox(bbox)
        elif place:
            nodes, roads = load_osm_online_place(place)
        else:
            raise ValueError("osm_online requires either bbox or place")
        return self._replace(nodes, roads, self.trajectories, self.geofences, self.pois)

    def rebuild_indexes(self) -> None:
        with self.lock:
            self.nodes = self.store.list_nodes()
            self.roads = self.store.list_roads()
            self.trajectories = self.store.list_trajectories()
            self.geofences = self.store.list_geofences()
            self.pois = self.store.list_pois()
            self.road_rtree = RTreeIndex(road_bbox_items(self.roads))
            self.road_kdtree = KDTree(road_centroid_items(self.roads))
            self.candidate_searcher = CandidateSearcher(self.roads, self.road_rtree, self.road_kdtree)
            self.graph = RoadGraph.build(self.nodes, self.roads)

    def roads_in_bbox(self, bbox: tuple[float, float, float, float]) -> list[RoadEdge]:
        ids = set(self.road_rtree.query(bbox))
        return [road for road in self.roads if road.id in ids]

    def roads_in_polygon(self, polygon: list[list[tuple[float, float]]]) -> list[RoadEdge]:
        polygon_bbox = bbox_of_polygon(polygon)
        candidates = self.roads_in_bbox(polygon_bbox)
        return [road for road in candidates if polyline_intersects_polygon(road.geometry, polygon)]

    def points_in_polygon(
        self,
        polygon: list[list[tuple[float, float]]],
        target: str = "trajectory_points",
    ) -> list[dict[str, Any]]:
        points: list[dict[str, Any]] = []
        if target == "pois":
            for poi in self.pois:
                if point_in_polygon(poi.coordinate, polygon) in {"inside", "boundary"}:
                    points.append({"id": poi.id, "name": poi.name, "lon": poi.lon, "lat": poi.lat})
            return points

        for trajectory in self.trajectories:
            for index, point in enumerate(trajectory.points):
                if point_in_polygon(point.coordinate, polygon) in {"inside", "boundary"}:
                    points.append(
                        {
                            "id": f"{trajectory.id}_{index}",
                            "trajectory_id": trajectory.id,
                            "point_index": index,
                            "lon": point.lon,
                            "lat": point.lat,
                            "timestamp": point.timestamp,
                        }
                    )
        return points

    def get_trajectory(self, trajectory_id: str | None = None) -> Trajectory | None:
        if trajectory_id:
            return next((trajectory for trajectory in self.trajectories if trajectory.id == trajectory_id), None)
        return self.trajectories[0] if self.trajectories else None

    def visualization_state(self) -> dict[str, Any]:
        return {
            "roads": feature_collection(road.to_geojson_feature() for road in self.roads),
            "trajectories": feature_collection(
                trajectory.to_geojson_feature() for trajectory in self.trajectories
            ),
            "geofences": feature_collection(geofence.to_geojson_feature() for geofence in self.geofences),
            "pois": feature_collection(poi.to_geojson_feature() for poi in self.pois),
            "bounds": self._bounds(),
        }

    def _replace(
        self,
        nodes: list[RoadNode],
        roads: list[RoadEdge],
        trajectories: list[Trajectory],
        geofences: list[GeoFence],
        pois: list[POI],
    ) -> dict[str, int]:
        self.store.replace_all(nodes, roads, trajectories, geofences, pois)
        self.rebuild_indexes()
        return {
            "nodes": len(self.nodes),
            "roads": len(self.roads),
            "trajectories": len(self.trajectories),
            "geofences": len(self.geofences),
            "pois": len(self.pois),
        }

    def _bounds(self) -> list[float] | None:
        boxes = [bbox_of_coords(road.geometry) for road in self.roads]
        if not boxes:
            return None
        return [
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        ]


_runtime: RuntimeState | None = None


def get_runtime() -> RuntimeState:
    global _runtime
    if _runtime is None:
        _runtime = RuntimeState()
    return _runtime


def trajectory_from_payload(payload: dict[str, Any]) -> Trajectory:
    points = [
        TrajectoryPoint(float(point["lon"]), float(point["lat"]), point.get("timestamp"))
        for point in payload.get("points", [])
    ]
    return Trajectory(str(payload.get("id") or "request_trajectory"), points)


def geofences_from_payload(payload: list[dict[str, Any]]) -> list[GeoFence]:
    geofences: list[GeoFence] = []
    for index, item in enumerate(payload):
        geometry = item.get("geometry") or {}
        geofences.append(
            GeoFence(
                id=str(item.get("id") or f"request_fence_{index}"),
                name=str(item.get("name") or item.get("id") or f"request_fence_{index}"),
                coordinates=normalize_polygon(geometry.get("coordinates") or item.get("coordinates") or []),
            )
        )
    return geofences

