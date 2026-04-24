from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Iterable, TypeVar

from app.core.bbox import BBox, bbox_center, bbox_intersects, bbox_union

T = TypeVar("T")


@dataclass(slots=True)
class _Entry(Generic[T]):
    bbox: BBox
    item: T


@dataclass(slots=True)
class _RNode(Generic[T]):
    bbox: BBox
    children: list["_RNode[T]"] = field(default_factory=list)
    entries: list[_Entry[T]] = field(default_factory=list)

    @property
    def leaf(self) -> bool:
        return bool(self.entries)


class RTreeIndex(Generic[T]):
    """Small static R-Tree-like index optimized for demo-size GIS datasets."""

    def __init__(self, items: Iterable[tuple[BBox, T]] = (), max_children: int = 8):
        self.max_children = max(2, max_children)
        self._entries = [_Entry(bbox, item) for bbox, item in items]
        self._root = self._build_entries(self._entries)

    def _build_entries(self, entries: list[_Entry[T]]) -> _RNode[T] | None:
        if not entries:
            return None
        if len(entries) <= self.max_children:
            return _RNode(bbox=bbox_union([entry.bbox for entry in entries]), entries=entries)

        spread_x = max(bbox_center(entry.bbox)[0] for entry in entries) - min(
            bbox_center(entry.bbox)[0] for entry in entries
        )
        spread_y = max(bbox_center(entry.bbox)[1] for entry in entries) - min(
            bbox_center(entry.bbox)[1] for entry in entries
        )
        axis = 0 if spread_x >= spread_y else 1
        entries.sort(key=lambda entry: bbox_center(entry.bbox)[axis])
        groups = [
            entries[index : index + self.max_children]
            for index in range(0, len(entries), self.max_children)
        ]
        children = [self._build_entries(group) for group in groups]
        real_children = [child for child in children if child is not None]
        return _RNode(
            bbox=bbox_union([child.bbox for child in real_children]),
            children=real_children,
        )

    def query(self, bbox: BBox) -> list[T]:
        if self._root is None:
            return []
        results: list[T] = []

        def visit(node: _RNode[T]) -> None:
            if not bbox_intersects(node.bbox, bbox):
                return
            if node.leaf:
                results.extend(entry.item for entry in node.entries if bbox_intersects(entry.bbox, bbox))
            else:
                for child in node.children:
                    visit(child)

        visit(self._root)
        return results

