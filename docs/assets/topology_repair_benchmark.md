# Topology Repair Benchmark

- Dataset: `synthetic_dirty_crossing_duplicate`
- Elapsed: `1.118 ms`

## Correctness

| Check | Passed |
| --- | ---: |
| duplicate_edges_removed | True |
| illegal_crossings_repaired | True |
| quality_score_improved | True |

## Before / After

| Metric | Before | After |
| --- | ---: | ---: |
| components | 2 | 5 |
| connected_components | 2 | 5 |
| crossing_without_node | 2 | 0 |
| dangling_edges | 3 | 4 |
| duplicate_edges | 1 | 0 |
| edge_count | 3 | 4 |
| illegal_crossings | 2 | 0 |
| isolated_nodes | 0 | 4 |
| issues | 6 | 8 |
| largest_component_ratio | 0.6 | 0.5555555555555556 |
| node_count | 5 | 9 |
| quality_score | 79.0 | 84.0 |
| self_intersections | 0 | 0 |
