from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Generic, Iterable, Protocol, TypeVar

from app.core.bbox import BBox, bbox_expand_m, bbox_intersects
from app.models.point import Coordinate

T = TypeVar("T")


@dataclass(slots=True)
class IndexedItem(Generic[T]):
    bbox: BBox
    item: T


@dataclass(slots=True)
class QueryStats(Generic[T]):
    items: list[T]
    latency_ms: float
    candidate_count: int
    false_positive_count: int = 0


class SpatialIndex(Protocol[T]):
    name: str

    def build(self, items: Iterable[tuple[BBox, T] | IndexedItem[T]]) -> "SpatialIndex[T]":
        ...

    def query_bbox(self, bbox: BBox) -> list[T]:
        ...

    def query_radius(self, point: Coordinate, radius_m: float) -> list[T]:
        ...

    def nearest(self, point: Coordinate, k: int = 1) -> list[T]:
        ...

    def stats(self) -> dict[str, Any]:
        ...

    def query(self, bbox: BBox) -> list[T]:
        ...

    def query_with_stats(self, bbox: BBox) -> QueryStats[T]:
        ...


class MeasuredIndex(Generic[T]):
    name = "measured"

    def __init__(self) -> None:
        self.items: list[IndexedItem[T]] = []

    def build(self, items: Iterable[tuple[BBox, T] | IndexedItem[T]]) -> "MeasuredIndex[T]":
        self.items = normalize_items(items)
        return self

    def query(self, bbox: BBox) -> list[T]:
        raise NotImplementedError

    def query_bbox(self, bbox: BBox) -> list[T]:
        return self.query(bbox)

    def query_radius(self, point: Coordinate, radius_m: float) -> list[T]:
        query_bbox = bbox_expand_m(point, radius_m)
        candidates = self.query_bbox(query_bbox)
        result: list[T] = []
        for entry in self.items:
            if entry.item in candidates and _bbox_distance_m(point, entry.bbox) <= radius_m:
                result.append(entry.item)
        return result

    def nearest(self, point: Coordinate, k: int = 1) -> list[T]:
        scored = sorted(
            ((_bbox_distance_m(point, entry.bbox), entry.item) for entry in self.items),
            key=lambda item: item[0],
        )
        return [item for _distance, item in scored[:k]]

    def stats(self) -> dict[str, Any]:
        return {"name": self.name, "item_count": len(self.items), "memory_estimate_bytes": len(self.items) * 96}

    def query_with_stats(self, bbox: BBox, exact_bboxes: dict[T, BBox] | None = None) -> QueryStats[T]:
        started = time.perf_counter()
        items = self.query(bbox)
        latency_ms = (time.perf_counter() - started) * 1000.0
        false_positive_count = 0
        if exact_bboxes is not None:
            false_positive_count = sum(1 for item in items if not bbox_intersects(exact_bboxes[item], bbox))
        return QueryStats(items, latency_ms, len(items), false_positive_count)


def normalize_items(items: Iterable[tuple[BBox, T] | IndexedItem[T]]) -> list[IndexedItem[T]]:
    result: list[IndexedItem[T]] = []
    for item in items:
        if isinstance(item, IndexedItem):
            result.append(item)
        else:
            bbox, value = item
            result.append(IndexedItem(bbox, value))
    return result


def bbox_distance_degrees(point: Coordinate, bbox: BBox) -> float:
    lon, lat = point
    dx = 0.0
    if lon < bbox[0]:
        dx = bbox[0] - lon
    elif lon > bbox[2]:
        dx = lon - bbox[2]
    dy = 0.0
    if lat < bbox[1]:
        dy = bbox[1] - lat
    elif lat > bbox[3]:
        dy = lat - bbox[3]
    return (dx * dx + dy * dy) ** 0.5


def _bbox_distance_m(point: Coordinate, bbox: BBox) -> float:
    lon_scale = max(0.1, abs(math.cos(math.radians(point[1]))))
    dx = 0.0
    if point[0] < bbox[0]:
        dx = (bbox[0] - point[0]) * 111_320.0 * lon_scale
    elif point[0] > bbox[2]:
        dx = (point[0] - bbox[2]) * 111_320.0 * lon_scale
    dy = 0.0
    if point[1] < bbox[1]:
        dy = (bbox[1] - point[1]) * 111_320.0
    elif point[1] > bbox[3]:
        dy = (point[1] - bbox[3]) * 111_320.0
    return (dx * dx + dy * dy) ** 0.5
