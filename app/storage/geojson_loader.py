from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.geojson import normalize_linestring, normalize_polygon
from app.core.geometry import polyline_length
from app.models import GeoFence, POI, RoadEdge, RoadNode, Trajectory, TrajectoryPoint


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _feature_id(feature: dict[str, Any], prefix: str, index: int) -> str:
    props = feature.get("properties") or {}
    return str(feature.get("id") or props.get("id") or f"{prefix}_{index:04d}")


def _node_id_from_coord(coord: tuple[float, float]) -> str:
    return f"node_{coord[0]:.7f}_{coord[1]:.7f}".replace(".", "_").replace("-", "m")


def _speed_limit(props: dict[str, Any]) -> float:
    value = props.get("speed_limit") or props.get("maxspeed") or 40
    if isinstance(value, str):
        digits = "".join(ch for ch in value if ch.isdigit() or ch == ".")
        return float(digits) if digits else 40.0
    return float(value)


def load_roads_geojson(path: str | Path) -> tuple[list[RoadNode], list[RoadEdge]]:
    return load_roads_collection(_read_json(path))


def load_roads_collection(collection: dict[str, Any]) -> tuple[list[RoadNode], list[RoadEdge]]:
    nodes_by_id: dict[str, RoadNode] = {}
    roads: list[RoadEdge] = []
    for index, feature in enumerate(collection.get("features", [])):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "LineString":
            continue
        props = feature.get("properties") or {}
        coords = normalize_linestring(geometry.get("coordinates") or [])
        if len(coords) < 2:
            continue
        from_node = str(props.get("from") or _node_id_from_coord(coords[0]))
        to_node = str(props.get("to") or _node_id_from_coord(coords[-1]))
        nodes_by_id.setdefault(from_node, RoadNode(from_node, coords[0][0], coords[0][1]))
        nodes_by_id.setdefault(to_node, RoadNode(to_node, coords[-1][0], coords[-1][1]))
        road = RoadEdge(
            id=_feature_id(feature, "edge", index),
            from_node=from_node,
            to_node=to_node,
            geometry=coords,
            length=float(props.get("length") or polyline_length(coords)),
            speed_limit=_speed_limit(props),
            road_type=str(props.get("road_type") or props.get("highway") or "residential"),
            oneway=bool(props.get("oneway", False)),
        )
        roads.append(road)
    return list(nodes_by_id.values()), roads


def load_trajectories_geojson(path: str | Path) -> list[Trajectory]:
    return load_trajectories_collection(_read_json(path))


def load_trajectories_collection(collection: dict[str, Any]) -> list[Trajectory]:
    trajectories: list[Trajectory] = []
    point_groups: dict[str, list[TrajectoryPoint]] = {}
    for index, feature in enumerate(collection.get("features", [])):
        geometry = feature.get("geometry") or {}
        props = feature.get("properties") or {}
        if geometry.get("type") == "LineString":
            coords = normalize_linestring(geometry.get("coordinates") or [])
            timestamps = props.get("timestamps") or [None] * len(coords)
            points = [
                TrajectoryPoint(lon, lat, timestamps[idx] if idx < len(timestamps) else None)
                for idx, (lon, lat) in enumerate(coords)
            ]
            trajectories.append(Trajectory(_feature_id(feature, "traj", index), points))
        elif geometry.get("type") == "Point":
            coord = normalize_linestring([geometry.get("coordinates")])[0]
            trajectory_id = str(props.get("trajectory_id") or "traj_points")
            point_groups.setdefault(trajectory_id, []).append(
                TrajectoryPoint(coord[0], coord[1], props.get("timestamp"))
            )
    trajectories.extend(Trajectory(traj_id, points) for traj_id, points in point_groups.items())
    return trajectories


def load_geofences_geojson(path: str | Path) -> list[GeoFence]:
    return load_geofences_collection(_read_json(path))


def load_geofences_collection(collection: dict[str, Any]) -> list[GeoFence]:
    geofences: list[GeoFence] = []
    for index, feature in enumerate(collection.get("features", [])):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "Polygon":
            continue
        props = feature.get("properties") or {}
        geofences.append(
            GeoFence(
                id=_feature_id(feature, "fence", index),
                name=str(props.get("name") or _feature_id(feature, "fence", index)),
                coordinates=normalize_polygon(geometry.get("coordinates") or []),
            )
        )
    return geofences


def load_pois_geojson(path: str | Path) -> list[POI]:
    return load_pois_collection(_read_json(path))


def load_pois_collection(collection: dict[str, Any]) -> list[POI]:
    pois: list[POI] = []
    for index, feature in enumerate(collection.get("features", [])):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "Point":
            continue
        props = dict(feature.get("properties") or {})
        lon, lat = normalize_linestring([geometry.get("coordinates")])[0]
        poi_id = _feature_id(feature, "poi", index)
        pois.append(
            POI(
                id=poi_id,
                name=str(props.pop("name", poi_id)),
                lon=lon,
                lat=lat,
                properties=props,
            )
        )
    return pois

