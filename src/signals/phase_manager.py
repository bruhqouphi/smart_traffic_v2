from enum import Enum, auto
from typing import Callable, List, Optional


class SignalState(Enum):
    GREEN = auto()
    YELLOW = auto()
    ALL_RED = auto()


class PhaseManager:
    """
    Single signal state machine used by both simulation engine and dashboard.
    Transition: GREEN -> YELLOW -> ALL_RED -> GREEN.
    Phase changes take effect when entering GREEN after ALL_RED.
    """

    def __init__(self, config: dict, initial_phase: str = "NS"):
        t = config["timing"]
        self.yellow_duration = float(t["yellow_duration"])
        self.all_red_duration = float(t["all_red_duration"])

        self.current_phase: str = initial_phase
        self.state: SignalState = SignalState.GREEN
        self.state_elapsed: float = 0.0
        self.green_duration: float = float(t["min_green"])
        self.cycle_count: int = 0

        self._pending_phase: Optional[str] = None
        self._pending_green_duration: Optional[float] = None
        self._on_phase_change_callbacks: List[Callable[[str], None]] = []

    def on_phase_change(self, callback: Callable[[str], None]):
        self._on_phase_change_callbacks.append(callback)

    def set_green_duration(self, duration: float):
        """Set green duration for the current (or upcoming) GREEN phase."""
        self.green_duration = float(duration)

    def request_phase_change(self, next_phase: str, green_duration: float):
        """Queue a phase + duration to apply when the next GREEN begins."""
        self._pending_phase = next_phase
        self._pending_green_duration = float(green_duration)

    def truncate_green(self, min_elapsed: float = 0.0) -> bool:
        """
        End the current green as early as `min_elapsed` seconds into it.

        Used by emergency preemption to cut a conflicting green short. Yellow
        and all-red still run in full — this shortens the wait for the next
        phase, it never shortens clearance. A no-op outside GREEN (the signal is
        already mid-transition) and never *extends* a green that was going to
        end sooner. Returns True if the green was actually shortened.
        """
        if self.state != SignalState.GREEN:
            return False
        target = max(float(min_elapsed), self.state_elapsed)
        if target >= self.green_duration:
            return False
        self.green_duration = target
        return True

    def hold_green(self, duration: float):
        """
        Extend the current green to at least `duration` seconds so it cannot
        expire while an emergency vehicle is still discharging.
        """
        self.green_duration = max(self.green_duration, float(duration))

    def step(self, dt: float) -> bool:
        """Advance state machine by dt seconds. Returns True on phase change."""
        self.state_elapsed += dt
        changed = False

        if self.state == SignalState.GREEN:
            if self.state_elapsed >= self.green_duration:
                self.state = SignalState.YELLOW
                self.state_elapsed = 0.0

        elif self.state == SignalState.YELLOW:
            if self.state_elapsed >= self.yellow_duration:
                self.state = SignalState.ALL_RED
                self.state_elapsed = 0.0

        elif self.state == SignalState.ALL_RED:
            if self.state_elapsed >= self.all_red_duration:
                # Apply queued phase/duration before entering GREEN
                if self._pending_phase is not None:
                    self.current_phase = self._pending_phase
                    self._pending_phase = None
                if self._pending_green_duration is not None:
                    self.green_duration = self._pending_green_duration
                    self._pending_green_duration = None
                self.state = SignalState.GREEN
                self.state_elapsed = 0.0
                self.cycle_count += 1
                changed = True
                for cb in self._on_phase_change_callbacks:
                    cb(self.current_phase)

        return changed

    def get_signal_colors(self) -> dict:
        """{"NS": "green"|"yellow"|"red", "EW": ...}"""
        other = "EW" if self.current_phase == "NS" else "NS"
        if self.state == SignalState.GREEN:
            return {self.current_phase: "green", other: "red"}
        if self.state == SignalState.YELLOW:
            return {self.current_phase: "yellow", other: "red"}
        return {"NS": "red", "EW": "red"}

    def is_green(self, phase: str) -> bool:
        return self.state == SignalState.GREEN and self.current_phase == phase

    def time_remaining(self) -> float:
        if self.state == SignalState.GREEN:
            return max(0.0, self.green_duration - self.state_elapsed)
        if self.state == SignalState.YELLOW:
            return max(0.0, self.yellow_duration - self.state_elapsed)
        return max(0.0, self.all_red_duration - self.state_elapsed)
