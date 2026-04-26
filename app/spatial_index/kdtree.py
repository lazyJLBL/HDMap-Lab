from __future__ import annotations

from typing import Generic, Iterable, TypeVar

from app.index.kdtree import KDTree
from app.models.point import Coordinate

T = TypeVar("T")


class KDTreePointIndex(Generic[T]):
    name = "kdtree"

    def __init__(self, items: Iterable[tuple[Coordinate, T]] = ()):
        self.tree = KDTree(items)

    def nearest(self, point: Coordinate, k: int = 1) -> list[T]:
        return self.tree.nearest(point, k)
