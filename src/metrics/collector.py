import csv
import os
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np


@dataclass
class QueueSnapshot:
    time: float
    queues: Dict[str, int]


@dataclass
class SignalCycleRecord:
    time: float
    phase: str
    green_duration: float


class MetricsCollector:
    def __init__(self):
        self.queue_snapshots: List[QueueSnapshot] = []
        self.signal_cycles: List[SignalCycleRecord] = []
        self.vehicle_waits: List[float] = []
        self.waits_by_approach: Dict[str, List[float]] = {}

    def record_queue_snapshot(self, t: float, queues: Dict[str, int]):
        self.queue_snapshots.append(QueueSnapshot(t, dict(queues)))

    def record_signal_cycle(self, t: float, phase: str, green_duration: float):
        self.signal_cycles.append(SignalCycleRecord(t, phase, green_duration))

    def record_vehicle_wait(self, wait: float, approach: str):
        self.vehicle_waits.append(wait)
        self.waits_by_approach.setdefault(approach, []).append(wait)

    def summary(self) -> dict:
        waits = self.vehicle_waits
        all_totals = [sum(s.queues.values()) for s in self.queue_snapshots]
        return {
            "avg_wait": float(np.mean(waits)) if waits else 0.0,
            "max_wait": float(np.max(waits)) if waits else 0.0,
            "avg_queue": float(np.mean(all_totals)) if all_totals else 0.0,
            "max_queue": float(np.max(all_totals)) if all_totals else 0.0,
            "throughput": len(waits),
            "num_cycles": len(self.signal_cycles),
        }

    def export_csv(self, directory: str, prefix: str = "traffic_metrics") -> dict:
        os.makedirs(directory, exist_ok=True)

        qpath = os.path.join(directory, f"{prefix}_queues.csv")
        with open(qpath, "w", newline="") as f:
            if self.queue_snapshots:
                approaches = list(self.queue_snapshots[0].queues.keys())
                writer = csv.DictWriter(f, fieldnames=["time"] + approaches)
                writer.writeheader()
                for snap in self.queue_snapshots:
                    row = {"time": snap.time, **snap.queues}
                    writer.writerow(row)

        wpath = os.path.join(directory, f"{prefix}_waits.csv")
        with open(wpath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["wait_time"])
            for w in self.vehicle_waits:
                writer.writerow([w])

        spath = os.path.join(directory, f"{prefix}_cycles.csv")
        with open(spath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["time", "phase", "green_duration"])
            writer.writeheader()
            for c in self.signal_cycles:
                writer.writerow({"time": c.time, "phase": c.phase,
                                  "green_duration": c.green_duration})

        return {"queues": qpath, "waits": wpath, "cycles": spath}


def run_statistical_trials(
    config: dict,
    algorithm_name: str,
    scenario: str,
    duration: float,
    n_trials: int = 10,
) -> dict:
    from src.signals.timing_algorithms import get_algorithm
    from src.simulation.sim_engine import SimEngine

    summaries = []
    for seed in range(n_trials):
        algo = get_algorithm(algorithm_name, config)
        engine = SimEngine(config, algo, scenario=scenario, seed=seed)
        summaries.append(engine.run(duration).summary())

    keys = list(summaries[0].keys())
    return {
        k: {
            "mean": float(np.mean([s[k] for s in summaries])),
            "std": float(np.std([s[k] for s in summaries])),
        }
        for k in keys
    }
