from abc import ABC, abstractmethod
from typing import Dict, Optional, Set

PHASES = ("NS", "EW")


def other_phase(phase: str) -> str:
    return "EW" if phase == "NS" else "NS"


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

    # Optional hooks. Controllers that track elapsed time or service history
    # override these; the rest inherit no-ops so every caller can drive any
    # controller — including a wrapped one — without isinstance checks.
    def update_sim_time(self, t: float) -> None:
        """Tell the controller the current simulation time."""

    def record_served(self, phase: str) -> None:
        """Tell the controller a phase has just begun being served."""


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


class LongestQueueFirstAlgorithm(QueueClearingAlgorithm):
    """
    Longest-queue-first (max-pressure) with aging.

    The delay-minimizing counterpart to the SJF-inspired QueueClearingAlgorithm:
    rather than serving the *shortest* queue first, always serve the phase with
    the *largest* total queue, so the most vehicles are cleared per green and
    phase switching (and its lost time) is minimized. Reuses the parent's aging,
    empty-approach handling, and queue-proportional green timing.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self._reason = "Longest-queue-first — initialized"

    def next_phase(self, queues: Dict[str, int], current_phase: str, elapsed: float) -> str:
        other = "EW" if current_phase == "NS" else "NS"

        # Aging: promote a starving phase regardless of its queue length.
        if self._is_starving(other):
            self._reason = (
                f"Aging: {other} not served for "
                f"{self._sim_time - self._last_served[other]:.0f}s — promoted"
            )
            return other

        ns_q = self._phase_total(queues, "NS")
        ew_q = self._phase_total(queues, "EW")

        # Don't waste a green phase on an empty approach when the other has vehicles.
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

        # Max-pressure: serve the larger queue to clear the most vehicles.
        choice = "NS" if ns_q >= ew_q else "EW"
        self._reason = (
            f"Longest-queue-first: {choice} larger "
            f"({self._phase_total(queues, choice)} veh)"
        )
        return choice


class EmergencyPreemptionController(TimingAlgorithm):
    """
    Emergency-vehicle preemption — the highest tier of the priority hierarchy.

    This is a *wrapper*, not a fifth algorithm. It decorates any base controller
    and takes over phase selection only while an emergency vehicle is waiting;
    the rest of the time every decision passes straight through. Structuring it
    this way means all four controllers gain preemption without duplicating a
    line of their logic, and the with/without comparison is a like-for-like test
    of the same base strategy.

    Sequence, once an EV is detected on a phase:

    1. That phase becomes the target. If it is already green, the green is held
       (up to `max_preempt_green`) so the interval cannot expire under the EV.
    2. If the conflicting phase is green, its green is truncated — but not
       before `min_green_before_preempt` seconds have been served, because
       dropping a green instantly strands vehicles already moving into the
       junction. The signal still runs its full yellow and all-red before the
       target turns green; preemption skips the *wait*, never the clearance.
    3. The target is held green until the last EV has departed, plus
       `clearance_extension` seconds for it to clear the junction, after which
       control returns to the base controller.

    If both phases have an EV, the one already being served wins, so the
    controller finishes clearing it rather than oscillating between the two.
    """

    def __init__(self, base: TimingAlgorithm, config: dict):
        e = config.get("emergency") or {}
        t = config["timing"]
        self.base = base
        self.min_green_before_preempt = float(e.get("min_green_before_preempt", 0.0))
        self.max_preempt_green = float(e.get("max_preempt_green", t["max_green"]))
        self.clearance_extension = float(e.get("clearance_extension", 0.0))
        if self.max_preempt_green <= 0:
            raise ValueError("emergency.max_preempt_green must be positive")
        if self.min_green_before_preempt < 0 or self.clearance_extension < 0:
            raise ValueError("emergency timing values must not be negative")

        self._target: Optional[str] = None
        self._release_at: Optional[float] = None
        self._sim_time = 0.0
        self.preemption_count = 0
        self._reason = "Preemption armed — no emergency vehicle"

    # -- state ---------------------------------------------------------------
    @property
    def is_preempting(self) -> bool:
        return self._target is not None

    @property
    def target_phase(self) -> Optional[str]:
        return self._target

    def notify_emergency(self, phases: Set[str], current_phase: str) -> bool:
        """
        Report which phases currently have a waiting EV.

        Returns True on the tick a *new* preemption begins, so the caller can
        count it. Must be called every tick for the clearance timer to run.
        """
        if phases:
            # Prefer the phase being served: finish clearing it rather than
            # oscillating when both approaches have an emergency vehicle.
            target = current_phase if current_phase in phases else sorted(phases)[0]
            self._release_at = None
            if self._target is None:
                self._target = target
                self.preemption_count += 1
                self._reason = f"PREEMPT: emergency vehicle on {target} — clearing"
                return True
            self._target = target
            self._reason = f"PREEMPT: holding {target} for emergency vehicle"
            return False

        if self._target is not None:
            # Last EV has departed: hold the phase a little longer so it is
            # clear of the junction before conflicting movements are released.
            if self._release_at is None:
                self._release_at = self._sim_time + self.clearance_extension
                self._reason = (
                    f"PREEMPT: {self._target} clearing "
                    f"({self.clearance_extension:.0f}s extension)"
                )
            if self._sim_time >= self._release_at:
                self._target = None
                self._release_at = None
                self._reason = "Preemption released — normal control resumed"
        return False

    # -- TimingAlgorithm -----------------------------------------------------
    def next_phase(self, queues: Dict[str, int], current_phase: str, elapsed: float) -> str:
        if self._target is not None:
            return self._target
        return self.base.next_phase(queues, current_phase, elapsed)

    def green_duration(self, queues: Dict[str, int], phase: str) -> float:
        if self._target is not None and phase == self._target:
            return self.max_preempt_green
        return self.base.green_duration(queues, phase)

    def get_last_reason(self) -> str:
        if self._target is not None or self._release_at is not None:
            return self._reason
        return self.base.get_last_reason()

    def update_sim_time(self, t: float) -> None:
        self._sim_time = t
        self.base.update_sim_time(t)

    def record_served(self, phase: str) -> None:
        self.base.record_served(phase)


ALGORITHMS = {
    "fixed": FixedTimingAlgorithm,
    "proportional": ProportionalTimingAlgorithm,
    "queue_clearing": QueueClearingAlgorithm,
    "longest_queue_first": LongestQueueFirstAlgorithm,
}


def get_algorithm(name: str, config: dict) -> TimingAlgorithm:
    """The bare controller, with no emergency wrapper. See build_controller."""
    key = name.lower().replace("-", "_")
    if key not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm '{name}'. Choose from: {list(ALGORITHMS)}")
    return ALGORITHMS[key](config)


def emergency_enabled(config: dict) -> bool:
    return bool((config.get("emergency") or {}).get("enabled", False))


def build_controller(name: str, config: dict) -> TimingAlgorithm:
    """
    The controller as it should actually be run: the named algorithm, wrapped in
    emergency preemption when the config enables it. A config with no
    `emergency:` block returns the bare controller, exactly as before.
    """
    base = get_algorithm(name, config)
    if emergency_enabled(config):
        return EmergencyPreemptionController(base, config)
    return base
