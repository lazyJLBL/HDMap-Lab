from __future__ import annotations

from app.models.point import Coordinate

BBox = tuple[float, float, float, float]


def bbox_of_coords(coords: list[Coordinate]) -> BBox:
    if not coords:
        raise ValueError("Cannot build a bbox from empty coordinates")
    lons = [coord[0] for coord in coords]
    lats = [coord[1] for coord in coords]
    return min(lons), min(lats), max(lons), max(lats)


def bbox_of_polygon(rings: list[list[Coordinate]]) -> BBox:
    coords = [coord for ring in rings for coord in ring]
    return bbox_of_coords(coords)


def bbox_intersects(left: BBox, right: BBox) -> bool:
    return not (
        left[2] < right[0]
        or left[0] > right[2]
        or left[3] < right[1]
        or left[1] > right[3]
    )


def bbox_contains_point(bbox: BBox, point: Coordinate) -> bool:
    lon, lat = point
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def bbox_center(bbox: BBox) -> Coordinate:
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def bbox_expand_m(point: Coordinate, radius_m: float) -> BBox:
    lon, lat = point
    lat_delta = radius_m / 111_320.0
    lon_scale = max(0.1, abs(__import__("math").cos(__import__("math").radians(lat))))
    lon_delta = radius_m / (111_320.0 * lon_scale)
    return lon - lon_delta, lat - lat_delta, lon + lon_delta, lat + lat_delta


def bbox_union(boxes: list[BBox]) -> BBox:
    if not boxes:
        raise ValueError("Cannot union empty bboxes")
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )

