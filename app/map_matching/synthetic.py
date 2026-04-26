from __future__ import annotations

import random
from dataclasses import dataclass

from app.geometry_kernel.polyline import _from_xy, point_to_segment_projection
from app.models import RoadEdge, Trajectory, TrajectoryPoint
from app.models.point import Coordinate


@dataclass(slots=True)
class SyntheticCase:
    name: str
    trajectory: Trajectory
    ground_truth_roads: list[str]
    description: str


def generate_noisy_trace(
    name: str,
    route: list[RoadEdge],
    samples_per_edge: int = 4,
    noise_m: float = 8.0,
    drift_m: tuple[float, float] = (0.0, 0.0),
    seed: int = 7,
) -> SyntheticCase:
    random.seed(seed)
    points: list[TrajectoryPoint] = []
    for edge in route:
        start, end = edge.geometry[0], edge.geometry[-1]
        for sample in range(samples_per_edge):
            t = sample / max(samples_per_edge - 1, 1)
            lon = start[0] + (end[0] - start[0]) * t
            lat = start[1] + (end[1] - start[1]) * t
            noisy = _offset_point((lon, lat), random.gauss(drift_m[0], noise_m), random.gauss(drift_m[1], noise_m))
            points.append(TrajectoryPoint(noisy[0], noisy[1], None))
    return SyntheticCase(
        name=name,
        trajectory=Trajectory(name, points),
        ground_truth_roads=[edge.id for edge in route],
        description=f"synthetic trace with {noise_m}m Gaussian noise and drift {drift_m}",
    )


def generate_parallel_road_case(route: list[RoadEdge], drift_m: float = 18.0) -> SyntheticCase:
    return generate_noisy_trace("parallel_roads", route, samples_per_edge=5, noise_m=4.0, drift_m=(0.0, drift_m), seed=11)


def generate_low_frequency_case(route: list[RoadEdge]) -> SyntheticCase:
    return generate_noisy_trace("low_frequency_gps", route, samples_per_edge=2, noise_m=10.0, seed=17)


def _offset_point(point: Coordinate, dx_m: float, dy_m: float) -> Coordinate:
    return _from_xy((dx_m, dy_m), point)


def project_trace_to_route(trajectory: Trajectory, route: list[RoadEdge]) -> list[Coordinate]:
    route_points = [coord for edge in route for coord in edge.geometry]
    return [point_to_segment_projection(point.coordinate, route_points[0], route_points[-1]).projection for point in trajectory.points]
