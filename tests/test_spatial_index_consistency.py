from __future__ import annotations

from app.core.bbox import BBox
from app.spatial_index import (
    BasicRTreeIndex,
    BruteForceIndex,
    GridIndex,
    KDTreeIndex,
    MortonIndex,
    QuadTreeIndex,
    RTreeIndex,
    STRRTreeIndex,
)


def _items() -> list[tuple[BBox, str]]:
    return [
        ((0.0, 0.0, 0.001, 0.001), "a"),
        ((0.01, 0.01, 0.011, 0.011), "b"),
        ((0.02, 0.0, 0.021, 0.001), "c"),
        ((0.0005, 0.0005, 0.002, 0.002), "d"),
    ]


def _indexes(items: list[tuple[BBox, str]]):
    return [
        BruteForceIndex(items),
        GridIndex(items, cell_size_degrees=0.002),
        KDTreeIndex(items),
        QuadTreeIndex(items, max_entries=1),
        BasicRTreeIndex(items),
        RTreeIndex(items),
        STRRTreeIndex(items),
        MortonIndex(items),
    ]


def test_bbox_queries_match_brute_force() -> None:
    items = _items()
    query = (0.00075, 0.00075, 0.0015, 0.0015)
    expected = set(BruteForceIndex(items).query_bbox(query))

    for index in _indexes(items):
        assert set(index.query_bbox(query)) == expected
        assert set(index.query(query)) == expected
        assert index.stats()["item_count"] == len(items)


def test_radius_queries_have_full_recall() -> None:
    items = _items()
    point = (0.0, 0.0)
    expected = set(BruteForceIndex(items).query_radius(point, 200.0))

    assert expected == {"a", "d"}
    for index in _indexes(items):
        assert set(index.query_radius(point, 200.0)) == expected


def test_nearest_queries_match_exact_baseline() -> None:
    items = _items()
    point = (0.0, 0.0)
    expected = BruteForceIndex(items).nearest(point, k=2)

    for index in _indexes(items):
        assert index.nearest(point, k=2) == expected


def test_empty_and_single_item_indexes() -> None:
    for index in _indexes([]):
        assert index.query_bbox((0.0, 0.0, 1.0, 1.0)) == []
        assert index.query_radius((0.0, 0.0), 10.0) == []
        assert index.nearest((0.0, 0.0), k=1) == []

    single = [((1.0, 1.0, 1.001, 1.001), "single")]
    for index in _indexes(single):
        assert index.query_bbox((0.5, 0.5, 1.5, 1.5)) == ["single"]
        assert index.nearest((1.0, 1.0), k=1) == ["single"]


def test_bbox_query_includes_boundary_touching_items() -> None:
    items = [
        ((0.0, 0.0, 1.0, 1.0), "left"),
        ((1.0, 1.0, 2.0, 2.0), "corner_touch"),
        ((2.1, 2.1, 3.0, 3.0), "outside"),
    ]
    query = (1.0, 1.0, 2.0, 2.0)
    expected = set(BruteForceIndex(items).query_bbox(query))

    assert expected == {"left", "corner_touch"}
    for index in _indexes(items):
        assert set(index.query_bbox(query)) == expected
