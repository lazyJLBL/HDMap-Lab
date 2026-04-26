# Topology Repair

`app/topology/` validates and repairs dirty road networks.

Validation report:

- connected components
- isolated nodes
- dangling edges
- duplicate edges
- illegal crossings
- overlapping roads
- road self-intersections

Repair pipeline:

1. Snap close nodes within a configurable meter tolerance.
2. Split roads at non-endpoint intersections.
3. Remove duplicate undirected edges.
4. Rebuild endpoint nodes from repaired geometry.
5. Re-run topology validation and return before/after metrics.

API:

```text
POST /topology/validate
POST /topology/repair
```

`/topology/repair` returns `fixed_roads` as GeoJSON plus `topology_report` JSON. Passing `"apply": true` replaces the in-memory runtime network with the repaired graph.
