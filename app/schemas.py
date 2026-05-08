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
    emission_weight: float = Field(default=1.0, ge=0)
    transition_weight: float = Field(default=1.0, ge=0)
    heading_weight: float = Field(default=4.0, ge=0)
    turn_weight: float = Field(default=2.0, ge=0)
    road_class_weight: float = Field(default=5.0, ge=0)
    oneway_weight: float = Field(default=25.0, ge=0)
    layer_weight: float = Field(default=6.0, ge=0)
    speed_weight: float = Field(default=1.0, ge=0)


class RouteRequest(BaseModel):
    start: Coordinate = Field(min_length=2, max_length=2)
    end: Coordinate = Field(min_length=2, max_length=2)
    waypoints: list[Coordinate] = Field(default_factory=list)
    mode: Literal["shortest_distance", "shortest_time"] = "shortest_distance"
    algorithm: Literal["dijkstra", "astar"] = "astar"
    avoid_polygons: list[PolygonCoordinates] = Field(default_factory=list)


class TopologyRequest(BaseModel):
    snap_tolerance_m: float = Field(default=1.0, ge=0)
    apply: bool = False
    split_intersections: bool = True
    merge_collinear: bool = False
    dangling_mode: Literal["mark_only", "remove_short", "remove_all"] = "mark_only"
    dangling_length_threshold_m: float = Field(default=10.0, ge=0)
    respect_layers: bool = True
    preserve_metadata: bool = True
    return_debug_layers: bool = True


class TopologyValidateRequest(BaseModel):
    detect_crossings: bool = True
    detect_overlaps: bool = True
    detect_near_miss: bool = False
    near_miss_tolerance_m: float = Field(default=1.0, ge=0)
    respect_layers: bool = True
    return_debug_layers: bool = True


class SpatialIndexBenchmarkRequest(BaseModel):
    query_bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    iterations: int = Field(default=50, ge=1, le=500)
    dataset: Literal["synthetic_uniform", "synthetic_clustered", "osm_roads_sample"] = "synthetic_uniform"
    index_types: list[str] = Field(
        default_factory=lambda: ["brute", "grid", "kdtree", "quadtree", "rtree", "str_rtree", "morton"]
    )
    query_types: list[Literal["bbox", "radius", "nearest"]] = Field(default_factory=lambda: ["bbox"])
    query_count: int = Field(default=50, ge=1, le=5000)
    seed: int = 7
    radius_m: float = Field(default=150.0, gt=0)
    bbox_size_m: float = Field(default=250.0, gt=0)
    items: int = Field(default=1000, ge=1, le=100000)
    return_debug_layers: bool = False


class MapMatchingBenchmarkRequest(BaseModel):
    cases: list[str] = Field(default_factory=lambda: ["parallel_roads_drift", "low_frequency_sampling"])
    algorithms: list[Literal["nearest", "hmm"]] = Field(default_factory=lambda: ["nearest", "hmm"])
    noise_sigma_m: float = Field(default=4.0, ge=0)
    sampling_interval: int = Field(default=1, ge=1)
    k: int = Field(default=5, ge=1, le=20)
    radius_m: float = Field(default=150.0, gt=0)
    sigma: float = Field(default=20.0, gt=0)
    beta: float = Field(default=50.0, gt=0)
    emission_weight: float = Field(default=1.0, ge=0)
    transition_weight: float = Field(default=1.0, ge=0)
    heading_weight: float = Field(default=4.0, ge=0)
    turn_weight: float = Field(default=2.0, ge=0)
    road_class_weight: float = Field(default=5.0, ge=0)
    oneway_weight: float = Field(default=25.0, ge=0)
    layer_weight: float = Field(default=6.0, ge=0)
    speed_weight: float = Field(default=1.0, ge=0)
    return_debug_layers: bool = True


class TrajectoryAnalyzeRequest(BaseModel):
    trajectory_id: str | None = None
    trajectory: TrajectoryPayload | None = None
    reference: list[Coordinate] | None = None
    reference_route: list[Coordinate] | None = None
    methods: list[Literal["frechet", "hausdorff", "dtw", "simplification", "outlier", "deviation"]] = Field(
        default_factory=lambda: ["frechet", "hausdorff", "dtw", "simplification", "outlier", "deviation"]
    )
    simplify_tolerance_m: float = Field(default=5.0, ge=0)
    deviation_threshold_m: float = Field(default=30.0, ge=0)
    return_debug_layers: bool = True


class RouteExplainRequest(RouteRequest):
    preferred_road_classes: list[str] = Field(default_factory=list)
    prefer_road_classes: list[str] = Field(default_factory=list)
    avoid_road_classes: list[str] = Field(default_factory=list)
    cost_mode: Literal["distance", "time", "custom"] | None = None
    turn_cost: bool = True
    turn_penalty_seconds: float = Field(default=8.0, ge=0)
    avoid_mode: Literal["hard", "soft"] = "hard"
    custom_weights: dict[str, float] = Field(default_factory=dict)
    speed_profile: dict[str, float] = Field(default_factory=dict)
    return_debug_layers: bool = True
