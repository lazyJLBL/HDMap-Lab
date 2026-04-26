from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Generic, Iterable, Protocol, TypeVar

from app.core.bbox import BBox, bbox_intersects

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

    def query(self, bbox: BBox) -> list[T]:
        ...

    def query_with_stats(self, bbox: BBox) -> QueryStats[T]:
        ...


class MeasuredIndex(Generic[T]):
    name = "measured"

    def query(self, bbox: BBox) -> list[T]:
        raise NotImplementedError

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
