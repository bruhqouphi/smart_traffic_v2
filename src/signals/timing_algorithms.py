from abc import ABC, abstractmethod
from typing import Dict


class TimingAlgorithm(ABC):
    """Abstract base — all implementations must return phase IDs ("NS" or "EW")."""

    @abstractmethod
    def next_phase(self, queues: Dict[str, int], current_phase: str, elapsed: float) -> str:
        """Return the next phase ID to serve."""

    @abstractmethod
    def green_duration(self, queues: Dict[str, int], phase: str) -> float:
        """Return green duration in seconds for the given phase."""

    @abstractmethod
    def get_last_reason(self) -> str:
        """Human-readable explanation of the last decision."""


class FixedTimingAlgorithm(TimingAlgorithm):
    def __init__(self, config: dict):
        t = config["timing"]
        self._green = float(t["min_green"] + (t["max_green"] - t["min_green"]) // 2)
        self._reason = "Fixed timing — initialized"

    def next_phase(self, queues: Dict[str, int], current_phase: str, elapsed: float) -> str:
        nxt = "EW" if current_phase == "NS" else "NS"
        self._reason = f"Fixed: alternate to {nxt}"
        return nxt

    def green_duration(self, queues: Dict[str, int], phase: str) -> float:
        return self._green

    def get_last_reason(self) -> str:
        return self._reason


class ProportionalTimingAlgorithm(TimingAlgorithm):
    def __init__(self, config: dict):
        t = config["timing"]
        self.min_green = t["min_green"]
        self.max_green = t["max_green"]
        self._reason = "Proportional timing — initialized"

    def _phase_total(self, queues: Dict[str, int], phase: str) -> int:
        if phase == "NS":
            return queues.get("north", 0) + queues.get("south", 0)
        return queues.get("east", 0) + queues.get("west", 0)

    def next_phase(self, queues: Dict[str, int], current_phase: str, elapsed: float) -> str:
        nxt = "EW" if current_phase == "NS" else "NS"
        self._reason = f"Proportional: alternate to {nxt}"
        return nxt

    def green_duration(self, queues: Dict[str, int], phase: str) -> float:
        this_q = self._phase_total(queues, phase)
        other = "EW" if phase == "NS" else "NS"
        total = this_q + self._phase_total(queues, other)
        if total == 0:
            return float(self.min_green)
        ratio = this_q / total
        raw = self.min_green + ratio * (self.max_green - self.min_green)
        return float(max(self.min_green, min(self.max_green, raw)))

    def get_last_reason(self) -> str:
        return self._reason


class QueueClearingAlgorithm(TimingAlgorithm):
    """
    SJF-inspired queue-clearing with aging.

    Short queue (<=threshold): serve first (SJF).
    Both long: serve the larger queue.
    Aging: if an approach hasn't been served in >max_wait_threshold seconds,
    promote it regardless of queue length (prevents starvation).
    """

    def __init__(self, config: dict):
        t = config["timing"]
        qc = config["queue_clearing"]
        self.min_green = t["min_green"]
        self.max_green = t["max_green"]
        self.threshold = qc["short_queue_threshold"]
        self.short_green = float(qc["short_queue_green"])
        self.long_min = float(qc["long_queue_min_green"])
        self.long_max = float(qc["long_queue_max_green"])
        self.max_wait = float(t["max_wait_threshold"])
        self.startup_lost = float(t["startup_lost_time"])
        self.headway = float(t["headway"])

        self._last_served: Dict[str, float] = {"NS": 0.0, "EW": 0.0}
        self._sim_time: float = 0.0
        self._reason = "Queue-clearing — initialized"

    def update_sim_time(self, t: float):
        self._sim_time = t

    def record_served(self, phase: str):
        self._last_served[phase] = self._sim_time

    def _phase_total(self, queues: Dict[str, int], phase: str) -> int:
        if phase == "NS":
            return queues.get("north", 0) + queues.get("south", 0)
        return queues.get("east", 0) + queues.get("west", 0)

    def _is_starving(self, phase: str) -> bool:
        return (self._sim_time - self._last_served[phase]) > self.max_wait

    def next_phase(self, queues: Dict[str, int], current_phase: str, elapsed: float) -> str:
        other = "EW" if current_phase == "NS" else "NS"

        if self._is_starving(other):
            self._reason = (
                f"Aging: {other} not served for "
                f"{self._sim_time - self._last_served[other]:.0f}s — promoted"
            )
            return other

        ns_q = self._phase_total(queues, "NS")
        ew_q = self._phase_total(queues, "EW")

        # Don't waste a green phase on an empty approach when the other has vehicles
        if ns_q == 0 and ew_q == 0:
            nxt = "EW" if current_phase == "NS" else "NS"
            self._reason = "Both empty: alternate"
            return nxt
        if ns_q == 0:
            self._reason = f"NS empty; serve EW ({ew_q} veh)"
            return "EW"
        if ew_q == 0:
            self._reason = f"EW empty; serve NS ({ns_q} veh)"
            return "NS"

        ns_short = ns_q <= self.threshold
        ew_short = ew_q <= self.threshold

        if ns_short or ew_short:
            if ns_short and ew_short:
                choice = "NS" if ns_q <= ew_q else "EW"
            elif ns_short:
                choice = "NS"
            else:
                choice = "EW"
            self._reason = (
                f"SJF: {choice} has short queue "
                f"({self._phase_total(queues, choice)} veh ≤ {self.threshold})"
            )
            return choice

        choice = "NS" if ns_q >= ew_q else "EW"
        self._reason = (
            f"Long queues: {choice} larger "
            f"({self._phase_total(queues, choice)} veh)"
        )
        return choice

    def green_duration(self, queues: Dict[str, int], phase: str) -> float:
        q = self._phase_total(queues, phase)
        if q <= self.threshold:
            return self.short_green
        raw = self.startup_lost + q * self.headway
        return float(max(self.long_min, min(self.long_max, raw)))

    def get_last_reason(self) -> str:
        return self._reason


ALGORITHMS = {
    "fixed": FixedTimingAlgorithm,
    "proportional": ProportionalTimingAlgorithm,
    "queue_clearing": QueueClearingAlgorithm,
}


def get_algorithm(name: str, config: dict) -> TimingAlgorithm:
    key = name.lower().replace("-", "_")
    if key not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm '{name}'. Choose from: {list(ALGORITHMS)}")
    return ALGORITHMS[key](config)
