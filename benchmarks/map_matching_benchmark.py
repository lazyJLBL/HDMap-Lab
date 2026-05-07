from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from app.map_matching import match_hmm, match_nearest
from app.map_matching.candidate_search import CandidateSearcher
from app.map_matching.evaluation import evaluate_match_result
from app.map_matching.synthetic import generate_synthetic_case
from app.routing.graph_builder import RoadGraph


def main() -> None:
    parser = argparse.ArgumentParser(description="Run HDMap-Lab map matching benchmark cases.")
    parser.add_argument("--cases", default="parallel_roads_drift,low_frequency_sampling,overpass_layer_confusion")
    parser.add_argument("--algorithms", default="nearest,hmm")
    parser.add_argument("--output", type=Path, default=Path("docs/assets/map_matching_benchmark.json"))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--radius-m", type=float, default=150.0)
    parser.add_argument("--noise-sigma-m", type=float, default=4.0)
    parser.add_argument("--sampling-interval", type=int, default=1)
    args = parser.parse_args()

    case_ids = [item.strip() for item in args.cases.split(",") if item.strip()]
    algorithms = {item.strip() for item in args.algorithms.split(",") if item.strip()}
    rows = []
    for case_id in case_ids:
        case = generate_synthetic_case(case_id, noise_sigma_m=args.noise_sigma_m, sampling_interval=args.sampling_interval)
        searcher = CandidateSearcher(case.roads)
        graph = RoadGraph.build(case.nodes, case.roads)
        row = {"case_id": case.case_id, "description": case.description, "ground_truth": case.ground_truth_road_sequence}
        if "nearest" in algorithms:
            started = time.perf_counter()
            nearest = match_nearest(case.trajectory, searcher, args.k)
            row["nearest"] = evaluate_match_result(nearest, case, latency_ms=(time.perf_counter() - started) * 1000.0)
        if "hmm" in algorithms:
            started = time.perf_counter()
            hmm = match_hmm(case.trajectory, searcher, graph, k=args.k, radius_m=args.radius_m)
            row["hmm"] = evaluate_match_result(hmm, case, latency_ms=(time.perf_counter() - started) * 1000.0)
        rows.append(row)

    payload = {"cases": rows, "algorithms": sorted(algorithms)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("| Case | Algorithm | Seq accuracy | F1 | Latency ms | Candidate avg |")
    print("| --- | --- | ---: | ---: | ---: | ---: |")
    for row in rows:
        for algorithm in sorted(algorithms):
            metrics = row.get(algorithm)
            if not metrics:
                continue
            print(
                f"| {row['case_id']} | {algorithm} | {metrics['sequence_accuracy']:.3f} | "
                f"{metrics['f1']:.3f} | {metrics['latency_ms']:.3f} | {metrics['candidate_count_avg']:.2f} |"
            )
    print(f"output: {args.output}")


if __name__ == "__main__":
    main()
