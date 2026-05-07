from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Iterable, TypeVar

from app.core.bbox import BBox, bbox_center, bbox_intersects, bbox_union
from app.spatial_index.base import IndexedItem, MeasuredIndex, normalize_items

T = TypeVar("T")


@dataclass(slots=True)
class _MortonEntry(Generic[T]):
    code: int
    entry: IndexedItem[T]


class MortonIndex(MeasuredIndex[T], Generic[T]):
    """Static Z-order index over bbox centroids.

    The implementation sorts bbox centers by Morton code. Query filtering stays
    exact so the benchmark can compare correctness against brute force while
    exposing Z-order locality and memory behavior.
    """

    name = "morton"

    def __init__(self, items: Iterable[tuple[BBox, T] | IndexedItem[T]] = (), bits: int = 16):
        self.bits = max(1, min(bits, 24))
        self.bounds: BBox = (0.0, 0.0, 0.0, 0.0)
        self.encoded_items: list[_MortonEntry[T]] = []
        self.build(items)

    def build(self, items: Iterable[tuple[BBox, T] | IndexedItem[T]]) -> "MortonIndex[T]":
        self.items = normalize_items(items)
        self.bounds = bbox_union([entry.bbox for entry in self.items]) if self.items else (0.0, 0.0, 0.0, 0.0)
        self.encoded_items = sorted(
            (_MortonEntry(self._code_for_bbox(entry.bbox), entry) for entry in self.items),
            key=lambda item: item.code,
        )
        return self

    def query(self, bbox: BBox) -> list[T]:
        return [encoded.entry.item for encoded in self.encoded_items if bbox_intersects(encoded.entry.bbox, bbox)]

    def stats(self) -> dict[str, object]:
        stats = super().stats()
        stats.update(
            {
                "bits": self.bits,
                "bounds": list(self.bounds),
                "encoded_count": len(self.encoded_items),
                "query_strategy": "z_order_sorted_exact_filter",
            }
        )
        return stats

    def _code_for_bbox(self, bbox: BBox) -> int:
        center = bbox_center(bbox)
        max_value = (1 << self.bits) - 1
        x = _normalize(center[0], self.bounds[0], self.bounds[2], max_value)
        y = _normalize(center[1], self.bounds[1], self.bounds[3], max_value)
        return _interleave_bits(x, y)


def _normalize(value: float, minimum: float, maximum: float, max_value: int) -> int:
    if maximum <= minimum:
        return 0
    scaled = (value - minimum) / (maximum - minimum)
    return max(0, min(max_value, round(scaled * max_value)))


def _interleave_bits(x: int, y: int) -> int:
    code = 0
    bit = 0
    while x or y:
        code |= (x & 1) << (2 * bit)
        code |= (y & 1) << (2 * bit + 1)
        x >>= 1
        y >>= 1
        bit += 1
    return code
