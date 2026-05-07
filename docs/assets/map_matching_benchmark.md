# Map Matching Benchmark

Synthetic stress cases compare nearest-road matching with HMM sequence matching.

| Case | Algorithm | Seq accuracy | F1 | Latency ms | Candidate avg |
| --- | --- | ---: | ---: | ---: | ---: |
| parallel_roads_drift | hmm | 0.417 | 0.500 | 3.758 | 5.00 |
| parallel_roads_drift | nearest | 0.000 | 0.000 | 0.942 | 5.00 |
| low_frequency_sampling | hmm | 0.500 | 0.800 | 1.839 | 5.00 |
| low_frequency_sampling | nearest | 0.250 | 0.400 | 0.538 | 5.00 |
| overpass_layer_confusion | hmm | 0.417 | 0.500 | 4.378 | 5.00 |
| overpass_layer_confusion | nearest | 0.417 | 0.500 | 1.088 | 5.00 |

Correctness is evaluated against each synthetic case's ground-truth road sequence.
Latency is measured on the local machine and should not be read as a city-scale production benchmark.
