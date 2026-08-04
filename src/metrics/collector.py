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


@dataclass
class PreemptionRecord:
    time: float
    phase: str


@dataclass
class EmergencyRecord:
    approach: str
    arrival_time: float
    departure_time: float
    wait: float


class MetricsCollector:
    def __init__(self):
        self.queue_snapshots: List[QueueSnapshot] = []
        self.signal_cycles: List[SignalCycleRecord] = []
        self.vehicle_waits: List[float] = []
        self.waits_by_approach: Dict[str, List[float]] = {}
        self.arrivals = 0
        self.blocked = 0
        self.blocked_by_approach: Dict[str, int] = {}
        # Emergency vehicles are also counted in vehicle_waits/throughput — they
        # are real vehicles — and tracked separately here so response time can be
        # reported on its own.
        self.emergency_records: List[EmergencyRecord] = []
        self.preemptions: List[PreemptionRecord] = []

    def record_queue_snapshot(self, t: float, queues: Dict[str, int]):
        self.queue_snapshots.append(QueueSnapshot(t, dict(queues)))

    def record_arrivals(self, arrivals: Dict[str, int], blocked: Dict[str, int] = None):
        """Count vehicles generated, and those turned away by a full approach."""
        self.arrivals += sum(arrivals.values())
        for approach, n in (blocked or {}).items():
            if n:
                self.blocked += n
                self.blocked_by_approach[approach] = (
                    self.blocked_by_approach.get(approach, 0) + n
                )

    def record_signal_cycle(self, t: float, phase: str, green_duration: float):
        self.signal_cycles.append(SignalCycleRecord(t, phase, green_duration))

    def record_vehicle_wait(self, wait: float, approach: str):
        self.vehicle_waits.append(wait)
        self.waits_by_approach.setdefault(approach, []).append(wait)

    def record_emergency_clearance(self, vehicle):
        """Log an emergency vehicle that has cleared the intersection."""
        self.emergency_records.append(EmergencyRecord(
            approach=vehicle.approach,
            arrival_time=vehicle.arrival_time,
            departure_time=vehicle.departure_time,
            wait=vehicle.wait_time,
        ))

    def record_preemption(self, t: float, phase: str):
        self.preemptions.append(PreemptionRecord(t, phase))

    def summary(self) -> dict:
        waits = self.vehicle_waits
        all_totals = [sum(s.queues.values()) for s in self.queue_snapshots]
        ev_waits = [r.wait for r in self.emergency_records]
        return {
            "avg_wait": float(np.mean(waits)) if waits else 0.0,
            "max_wait": float(np.max(waits)) if waits else 0.0,
            "avg_queue": float(np.mean(all_totals)) if all_totals else 0.0,
            "max_queue": float(np.max(all_totals)) if all_totals else 0.0,
            "throughput": len(waits),
            "num_cycles": len(self.signal_cycles),
            "blocked": self.blocked,
            # Share of demand that never got into the intersection because the
            # approach was full. 0 when storage is unlimited.
            "blocked_pct": (100.0 * self.blocked / self.arrivals) if self.arrivals else 0.0,
            # Emergency-vehicle response. All zero when preemption is disabled,
            # since no EVs are generated.
            "ev_served": len(ev_waits),
            "avg_ev_wait": float(np.mean(ev_waits)) if ev_waits else 0.0,
            "max_ev_wait": float(np.max(ev_waits)) if ev_waits else 0.0,
            "preemptions": len(self.preemptions),
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

        paths = {"queues": qpath, "waits": wpath, "cycles": spath}

        # Only written when preemption actually ran, so runs without emergency
        # vehicles produce exactly the same set of files as before.
        if self.emergency_records:
            epath = os.path.join(directory, f"{prefix}_emergency.csv")
            with open(epath, "w", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["approach", "arrival_time", "departure_time", "wait"]
                )
                writer.writeheader()
                for r in self.emergency_records:
                    writer.writerow({
                        "approach": r.approach,
                        "arrival_time": r.arrival_time,
                        "departure_time": r.departure_time,
                        "wait": r.wait,
                    })
            paths["emergency"] = epath

        return paths


def run_statistical_trials(
    config: dict,
    algorithm_name: str,
    scenario: str,
    duration: float,
    n_trials: int = 10,
) -> dict:
    from src.signals.timing_algorithms import build_controller
    from src.simulation.sim_engine import SimEngine

    summaries = []
    for seed in range(n_trials):
        algo = build_controller(algorithm_name, config)
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
