from __future__ import annotations

from typing import Generic, Iterable, TypeVar

from app.core.bbox import BBox, bbox_intersects
from app.spatial_index.base import IndexedItem, MeasuredIndex, normalize_items

T = TypeVar("T")


class BruteForceIndex(MeasuredIndex[T], Generic[T]):
    name = "brute_force"

    def __init__(self, items: Iterable[tuple[BBox, T] | IndexedItem[T]] = ()):
        self.items = normalize_items(items)

    def query(self, bbox: BBox) -> list[T]:
        return [entry.item for entry in self.items if bbox_intersects(entry.bbox, bbox)]
