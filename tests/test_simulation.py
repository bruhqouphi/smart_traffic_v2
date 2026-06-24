import pytest

from src.signals.timing_algorithms import get_algorithm
from src.simulation.sim_engine import SimEngine

BASE_CFG = {
    "timing": {
        "min_green": 10,
        "max_green": 60,
        "yellow_duration": 3,
        "all_red_duration": 2,
        "startup_lost_time": 2.0,
        "headway": 2.0,
        "max_wait_threshold": 60,
    },
    "queue_clearing": {
        "short_queue_threshold": 5,
        "short_queue_green": 15,
        "long_queue_min_green": 20,
        "long_queue_max_green": 60,
    },
    "scenarios": {
        "balanced": {"north": 0.3, "south": 0.3, "east": 0.3, "west": 0.3},
        "asymmetric": {"north": 0.7, "south": 0.1, "east": 0.1, "west": 0.1},
    },
}


def _run(algo_name, scenario, duration=120.0, seed=42, cfg=BASE_CFG):
    algo = get_algorithm(algo_name, cfg)
    return SimEngine(cfg, algo, scenario=scenario, seed=seed, dt=0.1).run(duration)


class TestSimulationMetrics:
    def test_queue_clearing_throughput_nonzero(self):
        m = _run("queue_clearing", "balanced")
        assert m.summary()["throughput"] > 0

    def test_queue_clearing_cycles_nonzero(self):
        m = _run("queue_clearing", "balanced")
        assert m.summary()["num_cycles"] > 0

    def test_queue_clearing_avg_wait_positive(self):
        m = _run("queue_clearing", "balanced")
        assert m.summary()["avg_wait"] > 0

    def test_fixed_runs_and_produces_cycles(self):
        m = _run("fixed", "balanced", duration=60.0)
        assert m.summary()["num_cycles"] > 0

    def test_proportional_runs_and_produces_cycles(self):
        m = _run("proportional", "balanced", duration=60.0)
        assert m.summary()["num_cycles"] > 0

    def test_queue_snapshots_recorded(self):
        algo = get_algorithm("fixed", BASE_CFG)
        engine = SimEngine(BASE_CFG, algo, scenario="balanced", seed=0, dt=0.1)
        metrics = engine.run(30.0)
        assert len(metrics.queue_snapshots) > 0

    def test_signal_cycles_recorded(self):
        m = _run("queue_clearing", "balanced", duration=120.0)
        assert len(m.signal_cycles) > 0

    def test_csv_export_creates_files(self, tmp_path):
        m = _run("fixed", "balanced", duration=30.0)
        paths = m.export_csv(str(tmp_path), "test")
        for path in paths.values():
            import os
            assert os.path.exists(path), f"Missing: {path}"

    def test_summary_keys_present(self):
        m = _run("fixed", "balanced", duration=30.0)
        s = m.summary()
        for key in ("avg_wait", "max_wait", "avg_queue", "max_queue",
                    "throughput", "num_cycles"):
            assert key in s


class TestQueueClearingServesVehicles:
    def test_vehicles_actually_depart(self):
        algo = get_algorithm("queue_clearing", BASE_CFG)
        engine = SimEngine(BASE_CFG, algo, scenario="balanced", seed=5, dt=0.1)
        metrics = engine.run(120.0)
        assert len(metrics.vehicle_waits) > 0

    def test_all_wait_times_non_negative(self):
        m = _run("queue_clearing", "balanced")
        assert all(w >= 0 for w in m.vehicle_waits)

    def test_queue_clearing_vs_fixed_asymmetric(self):
        """Queue-clearing should not be dramatically worse than fixed on asymmetric."""
        m_fixed = _run("fixed", "asymmetric", duration=300.0, seed=0)
        m_qc = _run("queue_clearing", "asymmetric", duration=300.0, seed=0)
        fixed_wait = m_fixed.summary()["avg_wait"]
        qc_wait = m_qc.summary()["avg_wait"]
        # Allow generous margin — the key property is QC doesn't catastrophically fail
        assert qc_wait <= fixed_wait * 2.0

    def test_get_state_returns_expected_keys(self):
        algo = get_algorithm("queue_clearing", BASE_CFG)
        engine = SimEngine(BASE_CFG, algo, scenario="balanced", seed=0, dt=0.1)
        engine.step()
        state = engine.get_state()
        for key in ("time", "phase", "signal_state", "queues",
                    "signal_colors", "time_remaining", "algorithm_reason"):
            assert key in state
