from __future__ import annotations

import math
from collections import defaultdict
from typing import Generic, Iterable, TypeVar

from app.core.bbox import BBox, bbox_intersects
from app.spatial_index.base import IndexedItem, MeasuredIndex, normalize_items

T = TypeVar("T")


class GridIndex(MeasuredIndex[T], Generic[T]):
    name = "grid"

    def __init__(self, items: Iterable[tuple[BBox, T] | IndexedItem[T]] = (), cell_size_degrees: float = 0.005):
        self.items = normalize_items(items)
        self.cell_size = max(cell_size_degrees, 1e-9)
        self.cells: dict[tuple[int, int], list[IndexedItem[T]]] = defaultdict(list)
        for entry in self.items:
            for cell in self._cells_for_bbox(entry.bbox):
                self.cells[cell].append(entry)

    def query(self, bbox: BBox) -> list[T]:
        seen: set[T] = set()
        results: list[T] = []
        for cell in self._cells_for_bbox(bbox):
            for entry in self.cells.get(cell, []):
                if entry.item in seen:
                    continue
                if bbox_intersects(entry.bbox, bbox):
                    seen.add(entry.item)
                    results.append(entry.item)
        return results

    def _cells_for_bbox(self, bbox: BBox) -> list[tuple[int, int]]:
        min_x = math.floor(bbox[0] / self.cell_size)
        min_y = math.floor(bbox[1] / self.cell_size)
        max_x = math.floor(bbox[2] / self.cell_size)
        max_y = math.floor(bbox[3] / self.cell_size)
        return [(x, y) for x in range(min_x, max_x + 1) for y in range(min_y, max_y + 1)]
