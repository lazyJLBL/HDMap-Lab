from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Coordinate = list[float]
PolygonCoordinates = list[list[Coordinate]]


class DatasetLoadRequest(BaseModel):
    source: Literal["sample", "geojson", "osm_file", "osm_online"] = "sample"
    roads_path: str | None = None
    trajectories_path: str | None = None
    geofences_path: str | None = None
    pois_path: str | None = None
    roads_geojson: dict[str, Any] | None = None
    trajectories_geojson: dict[str, Any] | None = None
    geofences_geojson: dict[str, Any] | None = None
    pois_geojson: dict[str, Any] | None = None
    osm_path: str | None = None
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    place: str | None = None


class SpatialQueryRequest(BaseModel):
    query_type: Literal["roads_in_bbox", "points_in_polygon", "roads_in_polygon"]
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    polygon: PolygonCoordinates | None = None
    target: Literal["trajectory_points", "pois"] = "trajectory_points"


class TrajectoryPointPayload(BaseModel):
    lon: float
    lat: float
    timestamp: str | None = None


class TrajectoryPayload(BaseModel):
    id: str = "request_trajectory"
    points: list[TrajectoryPointPayload]


class GeofencePayload(BaseModel):
    id: str
    name: str | None = None
    geometry: dict[str, Any]


class GeofenceCheckRequest(BaseModel):
    trajectory_id: str | None = None
    trajectory: TrajectoryPayload | None = None
    geofences: list[GeofencePayload] | None = None


class MapMatchRequest(BaseModel):
    trajectory_id: str | None = None
    trajectory: TrajectoryPayload | None = None
    algorithm: Literal["nearest", "candidate_cost", "hmm"] = "hmm"
    k: int = Field(default=5, ge=1, le=20)
    sigma: float = Field(default=20.0, gt=0)
    beta: float = Field(default=50.0, gt=0)


class RouteRequest(BaseModel):
    start: Coordinate = Field(min_length=2, max_length=2)
    end: Coordinate = Field(min_length=2, max_length=2)
    waypoints: list[Coordinate] = Field(default_factory=list)
    mode: Literal["shortest_distance", "shortest_time"] = "shortest_distance"
    algorithm: Literal["dijkstra", "astar"] = "astar"
    avoid_polygons: list[PolygonCoordinates] = Field(default_factory=list)

