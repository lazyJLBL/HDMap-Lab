from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.map_matching.evaluation import evaluate_case
from app.map_matching.synthetic import generate_low_frequency_case, generate_parallel_road_case
from app.storage.runtime import RuntimeState


def main() -> None:
    runtime = RuntimeState("data/benchmark.sqlite")
    runtime.load_sample()
    if runtime.candidate_searcher is None:
        raise RuntimeError("candidate searcher is not initialized")
    by_id = {road.id: road for road in runtime.roads}
    preferred = ["edge_h_01_11", "edge_h_11_21", "edge_v_21_22"]
    route = [by_id[road_id] for road_id in preferred] if all(road_id in by_id for road_id in preferred) else runtime.roads[:3]
    cases = [generate_parallel_road_case(route), generate_low_frequency_case(route)]
    print("| Case | Nearest precision | HMM precision | Nearest ms | HMM ms |")
    print("| --- | ---: | ---: | ---: | ---: |")
    for case in cases:
        result = evaluate_case(case, runtime.candidate_searcher, runtime.graph)
        print(
            f"| {result['case']} | {result['nearest']['precision']:.3f} | "
            f"{result['hmm']['precision']:.3f} | {result['nearest']['latency_ms']:.3f} | "
            f"{result['hmm']['latency_ms']:.3f} |"
        )


if __name__ == "__main__":
    main()
