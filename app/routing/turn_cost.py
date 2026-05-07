from __future__ import annotations

from app.geometry_kernel.polyline import angle_difference
from app.routing.graph_builder import GraphArc


def compute_turn_angle(previous: GraphArc | None, current: GraphArc) -> float:
    """Signed turn angle in degrees.

    Positive values are clockwise/right turns under compass bearing convention;
    negative values are counter-clockwise/left turns.
    """

    if previous is None:
        return 0.0
    return (current.heading - previous.heading + 180.0) % 360.0 - 180.0


def classify_turn(angle_degrees: float) -> str:
    magnitude = abs(angle_degrees)
    if magnitude <= 15.0:
        return "straight"
    if magnitude >= 165.0:
        return "u_turn"
    if magnitude <= 45.0:
        return "slight_right" if angle_degrees > 0 else "slight_left"
    if magnitude <= 120.0:
        return "right" if angle_degrees > 0 else "left"
    return "sharp_right" if angle_degrees > 0 else "sharp_left"


def turn_penalty_seconds(
    previous: GraphArc | None,
    current: GraphArc,
    penalty_seconds: float = 8.0,
) -> float:
    if previous is None:
        return 0.0
    turn_type = classify_turn(compute_turn_angle(previous, current))
    multipliers = {
        "straight": 0.0,
        "slight_left": 0.35,
        "slight_right": 0.35,
        "left": 1.0,
        "right": 0.8,
        "sharp_left": 1.6,
        "sharp_right": 1.4,
        "u_turn": 3.0,
    }
    return penalty_seconds * multipliers[turn_type]


def turn_cost_seconds(previous: GraphArc | None, current: GraphArc, penalty_seconds: float = 8.0) -> float:
    return turn_penalty_seconds(previous, current, penalty_seconds)


def restricted_turn(previous: GraphArc | None, current: GraphArc) -> bool:
    if previous is None:
        return False
    for rule in [*previous.turn_restrictions, *current.turn_restrictions]:
        from_edge = rule.get("from_edge") or rule.get("from") or rule.get("source")
        to_edge = rule.get("to_edge") or rule.get("to") or rule.get("target")
        restriction = str(rule.get("type") or rule.get("restriction") or "").lower()
        if from_edge and from_edge != previous.edge_id:
            continue
        if to_edge and to_edge != current.edge_id:
            continue
        if restriction.startswith("no_") or restriction in {"forbidden", "restricted", "no_turn"}:
            return True
        if restriction == "only_straight" and classify_turn(compute_turn_angle(previous, current)) != "straight":
            return True
    return False


def road_class_preference_cost(
    arc: GraphArc,
    preferred_classes: list[str] | None = None,
    avoided_classes: list[str] | None = None,
) -> float:
    penalty = 0.0
    if preferred_classes and arc.road_class not in preferred_classes:
        penalty += arc.length * 0.15
    if avoided_classes and arc.road_class in avoided_classes:
        penalty += arc.length * 2.0
    return penalty


def heading_change_degrees(previous: GraphArc | None, current: GraphArc) -> float:
    if previous is None:
        return 0.0
    return angle_difference(previous.heading, current.heading)
