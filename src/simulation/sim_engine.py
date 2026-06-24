from typing import Dict

from src.signals.phase_manager import PhaseManager, SignalState
from src.signals.timing_algorithms import TimingAlgorithm, QueueClearingAlgorithm
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
        self.intersection = Intersection(config)
        self.phase_manager = PhaseManager(config, initial_phase="NS")
        self.metrics = MetricsCollector()

        # Set green duration for the very first phase
        initial_green = algorithm.green_duration(self.intersection.queue_lengths(), "NS")
        self.phase_manager.set_green_duration(initial_green)

        # Register callback — fires each time a new GREEN phase begins
        self.phase_manager.on_phase_change(self._on_phase_change)

    def _on_phase_change(self, new_phase: str):
        """Called when a new GREEN phase starts. Decides and queues the next one."""
        if isinstance(self.algorithm, QueueClearingAlgorithm):
            self.algorithm.record_served(new_phase)
        queues = self.intersection.queue_lengths()
        next_p = self.algorithm.next_phase(queues, new_phase, self.t)
        duration = self.algorithm.green_duration(queues, next_p)
        self.phase_manager.request_phase_change(next_p, duration)
        self.metrics.record_signal_cycle(self.t, new_phase, self.phase_manager.green_duration)

    def step(self):
        if isinstance(self.algorithm, QueueClearingAlgorithm):
            self.algorithm.update_sim_time(self.t)

        # Vehicles arrive on every tick
        arrivals = self.generator.arrivals_all(self.dt)
        self.intersection.arrive(arrivals, self.t)

        # Vehicles depart only during GREEN
        if self.phase_manager.state == SignalState.GREEN:
            departed = self.intersection.depart_phase(
                self.phase_manager.current_phase, self.dt, self.t
            )
            for v in departed:
                if v.wait_time is not None:
                    self.metrics.record_vehicle_wait(v.wait_time, v.approach)

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
        }
