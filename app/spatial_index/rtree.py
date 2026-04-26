from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil, sqrt
from typing import Generic, Iterable, TypeVar

from app.core.bbox import BBox, bbox_center, bbox_intersects, bbox_union
from app.spatial_index.base import IndexedItem, MeasuredIndex, normalize_items

T = TypeVar("T")


@dataclass(slots=True)
class _RNode(Generic[T]):
    bbox: BBox
    children: list["_RNode[T]"] = field(default_factory=list)
    entries: list[IndexedItem[T]] = field(default_factory=list)

    @property
    def leaf(self) -> bool:
        return bool(self.entries)


class BasicRTreeIndex(MeasuredIndex[T], Generic[T]):
    name = "rtree"

    def __init__(self, items: Iterable[tuple[BBox, T] | IndexedItem[T]] = (), max_children: int = 8):
        self.max_children = max(2, max_children)
        self.entries = normalize_items(items)
        self.root = self._build(self.entries)

    def query(self, bbox: BBox) -> list[T]:
        return _query_node(self.root, bbox) if self.root is not None else []

    def _build(self, entries: list[IndexedItem[T]]) -> _RNode[T] | None:
        if not entries:
            return None
        if len(entries) <= self.max_children:
            return _RNode(bbox_union([entry.bbox for entry in entries]), entries=entries)
        spread_x = max(bbox_center(entry.bbox)[0] for entry in entries) - min(bbox_center(entry.bbox)[0] for entry in entries)
        spread_y = max(bbox_center(entry.bbox)[1] for entry in entries) - min(bbox_center(entry.bbox)[1] for entry in entries)
        axis = 0 if spread_x >= spread_y else 1
        entries = sorted(entries, key=lambda entry: bbox_center(entry.bbox)[axis])
        children = [
            child
            for child in (self._build(entries[index : index + self.max_children]) for index in range(0, len(entries), self.max_children))
            if child is not None
        ]
        return _RNode(bbox_union([child.bbox for child in children]), children=children)


class STRRTreeIndex(BasicRTreeIndex[T], Generic[T]):
    name = "str_rtree"

    def _build(self, entries: list[IndexedItem[T]]) -> _RNode[T] | None:
        if not entries:
            return None
        if len(entries) <= self.max_children:
            return _RNode(bbox_union([entry.bbox for entry in entries]), entries=entries)
        leaf_nodes = self._pack_leaves(entries)
        level = leaf_nodes
        while len(level) > self.max_children:
            groups = [level[index : index + self.max_children] for index in range(0, len(level), self.max_children)]
            level = [_RNode(bbox_union([node.bbox for node in group]), children=group) for group in groups]
        return _RNode(bbox_union([node.bbox for node in level]), children=level)

    def _pack_leaves(self, entries: list[IndexedItem[T]]) -> list[_RNode[T]]:
        slice_count = max(1, ceil(sqrt(len(entries) / self.max_children)))
        entries = sorted(entries, key=lambda entry: bbox_center(entry.bbox)[0])
        slice_size = ceil(len(entries) / slice_count)
        leaves: list[_RNode[T]] = []
        for start in range(0, len(entries), slice_size):
            chunk = sorted(entries[start : start + slice_size], key=lambda entry: bbox_center(entry.bbox)[1])
            for index in range(0, len(chunk), self.max_children):
                group = chunk[index : index + self.max_children]
                leaves.append(_RNode(bbox_union([entry.bbox for entry in group]), entries=group))
        return leaves


def _query_node(node: _RNode[T] | None, bbox: BBox) -> list[T]:
    if node is None or not bbox_intersects(node.bbox, bbox):
        return []
    if node.leaf:
        return [entry.item for entry in node.entries if bbox_intersects(entry.bbox, bbox)]
    results: list[T] = []
    for child in node.children:
        results.extend(_query_node(child, bbox))
    return results
