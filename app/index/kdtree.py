from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Generic, Iterable, TypeVar

from app.models.point import Coordinate

T = TypeVar("T")


@dataclass(slots=True)
class _KDNode(Generic[T]):
    point: Coordinate
    item: T
    axis: int
    left: "_KDNode[T] | None" = None
    right: "_KDNode[T] | None" = None


class KDTree(Generic[T]):
    def __init__(self, items: Iterable[tuple[Coordinate, T]] = ()):
        self._items = list(items)
        self._root = self._build(self._items, depth=0)

    def _build(self, items: list[tuple[Coordinate, T]], depth: int) -> _KDNode[T] | None:
        if not items:
            return None
        axis = depth % 2
        items.sort(key=lambda item: item[0][axis])
        mid = len(items) // 2
        return _KDNode(
            point=items[mid][0],
            item=items[mid][1],
            axis=axis,
            left=self._build(items[:mid], depth + 1),
            right=self._build(items[mid + 1 :], depth + 1),
        )

    @staticmethod
    def _approx_distance_sq(a: Coordinate, b: Coordinate) -> float:
        lon_scale = math.cos(math.radians((a[1] + b[1]) / 2.0))
        dx = (a[0] - b[0]) * lon_scale
        dy = a[1] - b[1]
        return dx * dx + dy * dy

    def nearest(self, point: Coordinate, k: int = 1) -> list[T]:
        if k <= 0 or not self._root:
            return []
        heap: list[tuple[float, int, T]] = []
        counter = 0

        def visit(node: _KDNode[T] | None) -> None:
            nonlocal counter
            if node is None:
                return
            dist_sq = self._approx_distance_sq(point, node.point)
            if len(heap) < k:
                heapq.heappush(heap, (-dist_sq, counter, node.item))
                counter += 1
            elif dist_sq < -heap[0][0]:
                heapq.heapreplace(heap, (-dist_sq, counter, node.item))
                counter += 1

            axis = node.axis
            delta = point[axis] - node.point[axis]
            near = node.left if delta < 0 else node.right
            far = node.right if delta < 0 else node.left
            visit(near)
            if len(heap) < k or delta * delta < -heap[0][0]:
                visit(far)

        visit(self._root)
        return [item for _, _, item in sorted(heap, reverse=True)]

