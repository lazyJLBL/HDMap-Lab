from __future__ import annotations

from app.spatial_index import BasicRTreeIndex, BruteForceIndex, GridIndex, QuadTreeIndex, STRRTreeIndex


def test_spatial_index_implementations_match_brute_force() -> None:
    items = [
        ((0.0, 0.0, 1.0, 1.0), "a"),
        ((2.0, 2.0, 3.0, 3.0), "b"),
        ((0.5, 0.5, 2.5, 2.5), "c"),
    ]
    query = (0.75, 0.75, 2.25, 2.25)
    expected = set(BruteForceIndex(items).query(query))
    for index in [GridIndex(items, 1.0), QuadTreeIndex(items), BasicRTreeIndex(items), STRRTreeIndex(items)]:
        assert set(index.query(query)) == expected
