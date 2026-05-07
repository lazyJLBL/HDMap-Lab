from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from app.geometry_kernel.polyline import _from_xy, point_to_segment_projection, polyline_length
from app.models import RoadEdge, RoadNode, Trajectory, TrajectoryPoint
from app.models.point import Coordinate


@dataclass(slots=True)
class SyntheticCase:
    name: str
    trajectory: Trajectory
    ground_truth_roads: list[str]
    description: str
    roads: list[RoadEdge] = field(default_factory=list)
    nodes: list[RoadNode] = field(default_factory=list)
    noise_config: dict[str, Any] = field(default_factory=dict)
    debug_layers: dict[str, Any] = field(default_factory=dict)

    @property
    def case_id(self) -> str:
        return self.name

    @property
    def ground_truth_road_sequence(self) -> list[str]:
        return self.ground_truth_roads

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "roads": [road.to_geojson_feature() for road in self.roads],
            "trajectory": [[point.lon, point.lat] for point in self.trajectory.points],
            "ground_truth_road_sequence": self.ground_truth_road_sequence,
            "noise_config": self.noise_config,
            "debug_layers": self.debug_layers,
            "description": self.description,
        }


SUPPORTED_CASES = [
    "straight_clean",
    "parallel_roads_drift",
    "low_frequency_sampling",
    "urban_canyon_drift",
    "intersection_ambiguity",
    "overpass_layer_confusion",
    "wrong_nearest_road",
    "gps_outliers",
    "missing_points",
    "u_turn_case",
    "one_way_violation_case",
]


def generate_synthetic_case(
    case_id: str,
    noise_sigma_m: float = 4.0,
    sampling_interval: int = 1,
    seed: int = 7,
) -> SyntheticCase:
    if case_id not in SUPPORTED_CASES:
        raise ValueError(f"Unsupported map matching synthetic case: {case_id}")
    random.seed(seed)
    roads, nodes = _base_roads()
    if case_id != "u_turn_case":
        roads = [road for road in roads if road.id not in {"main_0_rev", "main_1_rev"}]
    by_id = {road.id: road for road in roads}
    route = [by_id["main_0"], by_id["main_1"]]
    drift = (0.0, 0.0)
    outliers: dict[int, tuple[float, float]] = {}
    missing: set[int] = set()
    description = case_id
    extra_noise = noise_sigma_m

    if case_id == "straight_clean":
        extra_noise = 0.5
    elif case_id == "parallel_roads_drift":
        drift = (0.0, 7.0)
        extra_noise = 1.0
        description = "GPS is drifted toward a nearby parallel service road."
    elif case_id == "low_frequency_sampling":
        sampling_interval = max(sampling_interval, 3)
        extra_noise = max(noise_sigma_m, 6.0)
    elif case_id == "urban_canyon_drift":
        drift = (5.0, 10.0)
        extra_noise = max(noise_sigma_m, 10.0)
    elif case_id == "intersection_ambiguity":
        route = [by_id["main_0"], by_id["north_0"]]
        extra_noise = max(noise_sigma_m, 5.0)
    elif case_id == "overpass_layer_confusion":
        route = [by_id["main_0"], by_id["main_1"]]
        drift = (0.0, 0.0)
        extra_noise = 3.0
    elif case_id == "wrong_nearest_road":
        drift = (0.0, 8.5)
        extra_noise = 0.5
    elif case_id == "gps_outliers":
        outliers = {3: (0.0, 45.0), 6: (0.0, -35.0)}
        extra_noise = max(noise_sigma_m, 3.0)
    elif case_id == "missing_points":
        missing = {2, 4, 6}
        extra_noise = max(noise_sigma_m, 3.0)
    elif case_id == "u_turn_case":
        route = [by_id["main_0"], by_id["main_1"], by_id["main_1_rev"], by_id["main_0_rev"]]
        extra_noise = max(noise_sigma_m, 3.0)
    elif case_id == "one_way_violation_case":
        route = [by_id["oneway_forward"]]
        drift = (0.0, 0.0)
        extra_noise = max(noise_sigma_m, 2.0)

    trajectory = _trajectory_from_route(
        case_id,
        route,
        samples_per_edge=max(2, 6 // max(1, sampling_interval)),
        noise_m=extra_noise,
        drift_m=drift,
        outliers=outliers,
        missing=missing,
        seed=seed,
    )
    truth = [road.id for road in route for _ in range(max(2, 6 // max(1, sampling_interval)))]
    if missing:
        truth = [road_id for index, road_id in enumerate(truth) if index not in missing]
    return SyntheticCase(
        name=case_id,
        trajectory=trajectory,
        ground_truth_roads=truth,
        description=description,
        roads=roads,
        nodes=nodes,
        noise_config={"noise_sigma_m": extra_noise, "drift_m": drift, "sampling_interval": sampling_interval},
        debug_layers=_debug_layers(roads, trajectory, truth),
    )


def generate_all_synthetic_cases() -> list[SyntheticCase]:
    return [generate_synthetic_case(case_id) for case_id in SUPPORTED_CASES]


def generate_noisy_trace(
    name: str,
    route: list[RoadEdge],
    samples_per_edge: int = 4,
    noise_m: float = 8.0,
    drift_m: tuple[float, float] = (0.0, 0.0),
    seed: int = 7,
) -> SyntheticCase:
    trajectory = _trajectory_from_route(name, route, samples_per_edge, noise_m, drift_m, {}, set(), seed)
    return SyntheticCase(
        name=name,
        trajectory=trajectory,
        ground_truth_roads=[edge.id for edge in route for _ in range(samples_per_edge)],
        description=f"synthetic trace with {noise_m}m Gaussian noise and drift {drift_m}",
        roads=route,
        nodes=[],
        noise_config={"noise_sigma_m": noise_m, "drift_m": drift_m, "samples_per_edge": samples_per_edge},
        debug_layers=_debug_layers(route, trajectory, [edge.id for edge in route]),
    )


def generate_parallel_road_case(route: list[RoadEdge] | None = None, drift_m: float = 18.0) -> SyntheticCase:
    if route:
        return generate_noisy_trace("parallel_roads", route, samples_per_edge=5, noise_m=4.0, drift_m=(0.0, drift_m), seed=11)
    return generate_synthetic_case("parallel_roads_drift", seed=11)


def generate_low_frequency_case(route: list[RoadEdge] | None = None) -> SyntheticCase:
    if route:
        return generate_noisy_trace("low_frequency_gps", route, samples_per_edge=2, noise_m=10.0, seed=17)
    return generate_synthetic_case("low_frequency_sampling", seed=17)


def project_trace_to_route(trajectory: Trajectory, route: list[RoadEdge]) -> list[Coordinate]:
    route_points = [coord for edge in route for coord in edge.geometry]
    return [point_to_segment_projection(point.coordinate, route_points[0], route_points[-1]).projection for point in trajectory.points]


def _trajectory_from_route(
    name: str,
    route: list[RoadEdge],
    samples_per_edge: int,
    noise_m: float,
    drift_m: tuple[float, float],
    outliers: dict[int, tuple[float, float]],
    missing: set[int],
    seed: int,
) -> Trajectory:
    rng = random.Random(seed)
    points: list[TrajectoryPoint] = []
    point_index = 0
    for edge in route:
        start, end = edge.geometry[0], edge.geometry[-1]
        for sample in range(samples_per_edge):
            t = sample / max(samples_per_edge - 1, 1)
            lon = start[0] + (end[0] - start[0]) * t
            lat = start[1] + (end[1] - start[1]) * t
            dx = rng.gauss(drift_m[0], noise_m)
            dy = rng.gauss(drift_m[1], noise_m)
            if point_index in outliers:
                dx += outliers[point_index][0]
                dy += outliers[point_index][1]
            if point_index not in missing:
                noisy = _offset_point((lon, lat), dx, dy)
                points.append(TrajectoryPoint(noisy[0], noisy[1], None))
            point_index += 1
    return Trajectory(name, points)


def _base_roads() -> tuple[list[RoadEdge], list[RoadNode]]:
    coords = {
        "a": (116.390, 39.900),
        "b": (116.400, 39.900),
        "c": (116.410, 39.900),
        "p0": (116.390, 39.90008),
        "p1": (116.410, 39.90008),
        "n": (116.400, 39.910),
        "s": (116.400, 39.890),
        "o0": (116.396, 39.897),
        "o1": (116.406, 39.903),
    }
    nodes = [RoadNode(node_id, coord[0], coord[1]) for node_id, coord in coords.items()]
    roads = [
        _road("main_0", "a", "b", [coords["a"], coords["b"]], "primary", 50.0),
        _road("main_1", "b", "c", [coords["b"], coords["c"]], "primary", 50.0),
        _road("main_1_rev", "c", "b", [coords["c"], coords["b"]], "primary", 50.0),
        _road("main_0_rev", "b", "a", [coords["b"], coords["a"]], "primary", 50.0),
        _road("parallel_service", "p0", "p1", [coords["p0"], coords["p1"]], "service", 20.0),
        _road("north_0", "b", "n", [coords["b"], coords["n"]], "secondary", 35.0),
        _road("south_0", "s", "b", [coords["s"], coords["b"]], "secondary", 35.0),
        _road("overpass", "o0", "o1", [coords["o0"], coords["o1"]], "primary", 50.0, metadata={"layer": 1, "bridge": True}),
        _road("oneway_forward", "a", "b", [coords["a"], coords["b"]], "primary", 50.0, oneway=True),
    ]
    return roads, nodes


def _road(
    road_id: str,
    from_node: str,
    to_node: str,
    geometry: list[Coordinate],
    road_class: str,
    speed: float,
    oneway: bool = False,
    metadata: dict[str, Any] | None = None,
) -> RoadEdge:
    return RoadEdge(
        id=road_id,
        from_node=from_node,
        to_node=to_node,
        geometry=geometry,
        length=polyline_length(geometry),
        speed_limit=speed,
        road_class=road_class,
        road_type=road_class,
        oneway=oneway,
        direction="forward" if oneway else "both",
        metadata=metadata or {},
    )


def _offset_point(point: Coordinate, dx_m: float, dy_m: float) -> Coordinate:
    return _from_xy((dx_m, dy_m), point)


def _debug_layers(roads: list[RoadEdge], trajectory: Trajectory, truth: list[str]) -> dict[str, Any]:
    return {
        "roads": {"type": "FeatureCollection", "features": [road.to_geojson_feature() for road in roads]},
        "trajectory": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"layer": "gps_points", "index": index, "truth": truth[index] if index < len(truth) else None},
                    "geometry": {"type": "Point", "coordinates": [point.lon, point.lat]},
                }
                for index, point in enumerate(trajectory.points)
            ],
        },
    }
