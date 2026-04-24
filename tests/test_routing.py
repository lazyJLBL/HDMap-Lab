from __future__ import annotations

from app.routing.astar import shortest_path_astar
from app.routing.constraints import edges_intersecting_polygons
from app.routing.dijkstra import shortest_path


def test_dijkstra_and_astar_find_paths(runtime) -> None:
    start = runtime.graph.nearest_node_id((116.390, 39.900))
    end = runtime.graph.nearest_node_id((116.410, 39.920))
    assert start is not None
    assert end is not None

    dijkstra = shortest_path(runtime.graph, start, end)
    astar = shortest_path_astar(runtime.graph, start, end)

    assert dijkstra.found
    assert astar.found
    assert dijkstra.distance > 0
    assert astar.distance > 0


def test_avoid_polygon_blocks_edges(runtime) -> None:
    polygon = [
        [
            (116.398, 39.908),
            (116.406, 39.908),
            (116.406, 39.916),
            (116.398, 39.916),
            (116.398, 39.908),
        ]
    ]

    blocked = edges_intersecting_polygons(runtime.roads, [polygon])

    assert "edge_h_11_21" in blocked

