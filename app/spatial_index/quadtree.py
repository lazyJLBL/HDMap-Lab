from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Iterable, TypeVar

from app.core.bbox import BBox, bbox_intersects, bbox_union
from app.spatial_index.base import IndexedItem, MeasuredIndex, normalize_items

T = TypeVar("T")


@dataclass(slots=True)
class _QuadNode(Generic[T]):
    bbox: BBox
    entries: list[IndexedItem[T]] = field(default_factory=list)
    children: list["_QuadNode[T]"] = field(default_factory=list)


class QuadTreeIndex(MeasuredIndex[T], Generic[T]):
    name = "quadtree"

    def __init__(
        self,
        items: Iterable[tuple[BBox, T] | IndexedItem[T]] = (),
        max_entries: int = 12,
        max_depth: int = 10,
    ):
        self.items = normalize_items(items)
        self.max_entries = max(1, max_entries)
        self.max_depth = max_depth
        self.root = self._build(self.items, 0) if self.items else None

    def query(self, bbox: BBox) -> list[T]:
        if self.root is None:
            return []
        results: list[T] = []
        seen: set[T] = set()

        def visit(node: _QuadNode[T]) -> None:
            if not bbox_intersects(node.bbox, bbox):
                return
            for entry in node.entries:
                if entry.item not in seen and bbox_intersects(entry.bbox, bbox):
                    seen.add(entry.item)
                    results.append(entry.item)
            for child in node.children:
                visit(child)

        visit(self.root)
        return results

    def _build(self, entries: list[IndexedItem[T]], depth: int) -> _QuadNode[T]:
        node_bbox = bbox_union([entry.bbox for entry in entries])
        node = _QuadNode(node_bbox)
        if len(entries) <= self.max_entries or depth >= self.max_depth:
            node.entries = entries
            return node
        min_lon, min_lat, max_lon, max_lat = node_bbox
        mid_lon = (min_lon + max_lon) / 2.0
        mid_lat = (min_lat + max_lat) / 2.0
        quadrants: list[tuple[BBox, list[IndexedItem[T]]]] = [
            ((min_lon, min_lat, mid_lon, mid_lat), []),
            ((mid_lon, min_lat, max_lon, mid_lat), []),
            ((min_lon, mid_lat, mid_lon, max_lat), []),
            ((mid_lon, mid_lat, max_lon, max_lat), []),
        ]
        leftovers: list[IndexedItem[T]] = []
        for entry in entries:
            containing = [bucket for bucket_bbox, bucket in quadrants if _contains(bucket_bbox, entry.bbox)]
            if len(containing) == 1:
                containing[0].append(entry)
            else:
                leftovers.append(entry)
        node.entries = leftovers
        node.children = [self._build(bucket, depth + 1) for _, bucket in quadrants if bucket]
        return node


def _contains(outer: BBox, inner: BBox) -> bool:
    return outer[0] <= inner[0] and inner[2] <= outer[2] and outer[1] <= inner[1] and inner[3] <= outer[3]
