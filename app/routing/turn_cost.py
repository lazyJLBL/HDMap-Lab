from __future__ import annotations

from app.geometry_kernel.polyline import angle_difference
from app.routing.graph_builder import GraphArc


def turn_cost_seconds(previous: GraphArc | None, current: GraphArc, penalty_seconds: float = 8.0) -> float:
    if previous is None or previous.edge_id == current.edge_id:
        return 0.0
    angle = angle_difference(previous.heading, current.heading)
    if angle < 35:
        return 0.0
    if angle > 150:
        return penalty_seconds * 2.0
    return penalty_seconds * (angle / 90.0)


def road_class_preference_cost(arc: GraphArc, preferred_classes: list[str] | None = None) -> float:
    if not preferred_classes:
        return 0.0
    if arc.road_class in preferred_classes:
        return 0.0
    return arc.length * 0.15
