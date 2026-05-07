from __future__ import annotations

from typing import Generic, Iterable, TypeVar

from app.core.bbox import BBox, bbox_center, bbox_intersects
from app.index.kdtree import KDTree
from app.models.point import Coordinate
from app.spatial_index.base import IndexedItem, MeasuredIndex, normalize_items

T = TypeVar("T")


class KDTreePointIndex(Generic[T]):
    name = "kdtree"

    def __init__(self, items: Iterable[tuple[Coordinate, T]] = ()):
        self.build(items)

    def build(self, items: Iterable[tuple[Coordinate, T]]) -> "KDTreePointIndex[T]":
        self.items = list(items)
        self.tree = KDTree(self.items)
        return self

    def nearest(self, point: Coordinate, k: int = 1) -> list[T]:
        return self.tree.nearest(point, k)

    def stats(self) -> dict[str, object]:
        return {"name": self.name, "item_count": len(self.items)}


class KDTreeIndex(MeasuredIndex[T], Generic[T]):
    """BBox index backed by KD-tree centroids for nearest-point experiments.

    KD-trees are not naturally rectangle indexes, so bbox and radius queries keep
    exact bbox filtering. The centroid KD-tree is retained for engineering
    comparisons and nearest-candidate fallback behavior.
    """

    name = "kdtree"

    def __init__(self, items: Iterable[tuple[BBox, T] | IndexedItem[T]] = ()):
        self.center_items: list[tuple[Coordinate, T]] = []
        self.tree: KDTree[T] = KDTree()
        self.build(items)

    def build(self, items: Iterable[tuple[BBox, T] | IndexedItem[T]]) -> "KDTreeIndex[T]":
        self.items = normalize_items(items)
        self.center_items = [(bbox_center(entry.bbox), entry.item) for entry in self.items]
        self.tree = KDTree(self.center_items)
        return self

    def query(self, bbox: BBox) -> list[T]:
        return [entry.item for entry in self.items if bbox_intersects(entry.bbox, bbox)]

    def stats(self) -> dict[str, object]:
        stats = super().stats()
        stats.update({"center_count": len(self.center_items), "bbox_queries": "exact_scan"})
        return stats
