from typing import Dict, Optional

from src.signals.phase_manager import PhaseManager, SignalState
from src.signals.timing_algorithms import (
    EmergencyPreemptionController,
    TimingAlgorithm,
)
from src.simulation.traffic_generator import TrafficGenerator
from src.simulation.intersection import Intersection
from src.metrics.collector import MetricsCollector


class SimEngine:
    """Time-stepped simulation engine (default dt=0.1s)."""

    def __init__(
        self,
        config: dict,
        algorithm: TimingAlgorithm,
        scenario: str = "balanced",
        seed: int = 42,
        dt: float = 0.1,
    ):
        self.config = config
        self.algorithm = algorithm
        self.dt = dt
        self.t = 0.0

        self.generator = TrafficGenerator(config, scenario, seed)
        self.intersection = Intersection(config, seed=seed)
        self.phase_manager = PhaseManager(config, initial_phase="NS")
        self.metrics = MetricsCollector()

        # Seconds of yellow still usable for discharge. Configs written before
        # this key existed discharge on green only. Cannot exceed the interval.
        self.yellow_discharge_time = min(
            float(config["timing"].get("yellow_discharge_time", 0.0)),
            self.phase_manager.yellow_duration,
        )

        # Present only when the config enables emergency preemption.
        self.preemption: Optional[EmergencyPreemptionController] = (
            algorithm if isinstance(algorithm, EmergencyPreemptionController) else None
        )

        # Set green duration for the very first phase
        initial_green = algorithm.green_duration(self.intersection.queue_lengths(), "NS")
        self.phase_manager.set_green_duration(initial_green)

        # Register callback — fires each time a new GREEN phase begins
        self.phase_manager.on_phase_change(self._on_phase_change)

    def _on_phase_change(self, new_phase: str):
        """Called when a new GREEN phase starts. Decides and queues the next one."""
        self.algorithm.record_served(new_phase)
        self._request_next_phase(new_phase)
        self.metrics.record_signal_cycle(self.t, new_phase, self.phase_manager.green_duration)

    def _request_next_phase(self, from_phase: str):
        """Ask the controller what to serve next and queue it."""
        queues = self.intersection.queue_lengths()
        next_p = self.algorithm.next_phase(queues, from_phase, self.t)
        duration = self.algorithm.green_duration(queues, next_p)
        self.phase_manager.request_phase_change(next_p, duration)

    def _service_emergency(self):
        """
        Drive the preemption sequence. Runs every tick so the controller's
        clearance timer advances and a newly arrived EV is acted on immediately
        rather than at the next phase boundary.
        """
        if self.preemption is None:
            return

        pm = self.phase_manager
        was_preempting = self.preemption.is_preempting
        started = self.preemption.notify_emergency(
            self.intersection.emergency_phases(), pm.current_phase
        )
        if started:
            self.metrics.record_preemption(self.t, self.preemption.target_phase)

        if self.preemption.is_preempting:
            target = self.preemption.target_phase
            if pm.current_phase == target:
                # Already serving the EV — make sure the green cannot expire
                # underneath it while it is still discharging.
                if pm.state == SignalState.GREEN:
                    pm.hold_green(self.preemption.max_preempt_green)
            else:
                # Conflicting phase is being served: queue the target and cut
                # the green short, honouring the minimum-green safety floor.
                # Outside GREEN this only queues — yellow/all-red run in full.
                pm.request_phase_change(target, self.preemption.max_preempt_green)
                pm.truncate_green(self.preemption.min_green_before_preempt)
        elif was_preempting:
            # Released: hand the next decision back to the base controller and
            # end the held green so normal service resumes promptly.
            self._request_next_phase(pm.current_phase)
            pm.truncate_green(0.0)

    def _is_discharging(self) -> bool:
        """
        Vehicles leave during GREEN, and for the first yellow_discharge_time
        seconds of YELLOW — those already in the intersection clear on amber.
        The phase does not change until ALL_RED ends, so the same approaches
        are served throughout.
        """
        state = self.phase_manager.state
        if state == SignalState.GREEN:
            return True
        if state == SignalState.YELLOW:
            return self.phase_manager.state_elapsed < self.yellow_discharge_time
        return False

    def step(self):
        self.algorithm.update_sim_time(self.t)

        # Vehicles arrive on every tick; those that find their approach full
        # are turned away (spillback) rather than joining an unbounded queue.
        arrivals = self.generator.arrivals_all(self.dt)
        blocked = self.intersection.arrive(arrivals, self.t)
        self.metrics.record_arrivals(arrivals, blocked)

        # Emergency vehicles arrive on top of ordinary demand, jump their queue,
        # and are never blocked. No-op unless the config enables preemption.
        ev_approaches = self.generator.emergency_arrivals(self.dt)
        if ev_approaches:
            self.intersection.arrive_emergency(ev_approaches, self.t)

        self._service_emergency()

        if self._is_discharging():
            departed = self.intersection.depart_phase(
                self.phase_manager.current_phase, self.dt, self.t
            )
            for v in departed:
                if v.wait_time is not None:
                    self.metrics.record_vehicle_wait(v.wait_time, v.approach)
                    if v.is_emergency:
                        self.metrics.record_emergency_clearance(v)

        self.metrics.record_queue_snapshot(self.t, self.intersection.queue_lengths())
        self.phase_manager.step(self.dt)
        self.t += self.dt

    def run(self, duration: float) -> MetricsCollector:
        steps = int(duration / self.dt)
        for _ in range(steps):
            self.step()
        return self.metrics

    def get_state(self) -> dict:
        return {
            "time": self.t,
            "phase": self.phase_manager.current_phase,
            "signal_state": self.phase_manager.state.name,
            "queues": self.intersection.queue_lengths(),
            "signal_colors": self.phase_manager.get_signal_colors(),
            "time_remaining": self.phase_manager.time_remaining(),
            "algorithm_reason": self.algorithm.get_last_reason(),
            "emergency_approaches": sorted(self.intersection.emergency_approaches()),
            "preempting": self.preemption.is_preempting if self.preemption else False,
        }
