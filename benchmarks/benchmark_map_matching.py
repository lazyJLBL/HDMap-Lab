from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.map_matching import match_candidate_cost, match_hmm, match_nearest
from app.models import Trajectory, TrajectoryPoint
from app.storage.runtime import RuntimeState


def expand_trajectory(base: Trajectory, repeat: int) -> Trajectory:
    points: list[TrajectoryPoint] = []
    for _ in range(repeat):
        points.extend(base.points)
    return Trajectory("bench_traj", points)


def timed(label: str, func):
    started = time.perf_counter()
    result = func()
    elapsed_ms = (time.perf_counter() - started) * 1000
    return label, elapsed_ms, len(result["matches"])


def main() -> None:
    runtime = RuntimeState("data/benchmark.sqlite")
    runtime.load_sample()
    base = runtime.get_trajectory("traj_001")
    if base is None or runtime.candidate_searcher is None:
        raise RuntimeError("sample trajectory is missing")
    trajectory = expand_trajectory(base, 20)

    rows = [
        timed("nearest 120 points", lambda: match_nearest(trajectory, runtime.candidate_searcher, 5)),
        timed("candidate_cost 120 points", lambda: match_candidate_cost(trajectory, runtime.candidate_searcher, runtime.graph, 5)),
        timed("hmm 120 points", lambda: match_hmm(trajectory, runtime.candidate_searcher, runtime.graph, 5)),
    ]

    print("| Scenario | Time ms | Matches |")
    print("| --- | ---: | ---: |")
    for label, elapsed_ms, count in rows:
        print(f"| {label} | {elapsed_ms:.3f} | {count} |")


if __name__ == "__main__":
    main()
