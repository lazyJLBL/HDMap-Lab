# Spatial Index Benchmark

- Dataset: `osm_roads_sample`
- Items: `13`
- Queries per type: `100`

| Index | Query | Build ms | p50 ms | p95 ms | p99 ms | Avg candidates | Recall | False positive | Memory bytes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| brute_force | bbox | 0.004 | 0.0012 | 0.0015 | 0.0022 | 0.77 | 1.000 | 0.000 | 1248 |
| grid | bbox | 0.060 | 0.0017 | 0.0027 | 0.0041 | 0.77 | 1.000 | 0.000 | 1248 |
| quadtree | bbox | 0.036 | 0.0020 | 0.0033 | 0.0541 | 0.77 | 1.000 | 0.000 | 1248 |
| rtree | bbox | 0.042 | 0.0012 | 0.0018 | 0.0021 | 0.77 | 1.000 | 0.000 | 1248 |
| str_rtree | bbox | 0.023 | 0.0012 | 0.0018 | 0.0020 | 0.77 | 1.000 | 0.000 | 1248 |
| kdtree | bbox | 0.027 | 0.0011 | 0.0013 | 0.0014 | 0.77 | 1.000 | 0.000 | 1248 |

Recall is measured against brute force. False positives are allowed for prefilter indexes, but exact filters here keep them near zero.
