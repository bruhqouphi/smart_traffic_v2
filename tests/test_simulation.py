import copy

import pytest

from src.signals.phase_manager import SignalState
from src.signals.timing_algorithms import get_algorithm
from src.simulation.intersection import Intersection
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


def _cfg_with(**timing):
    """BASE_CFG with the given timing keys overridden."""
    cfg = copy.deepcopy(BASE_CFG)
    cfg["timing"].update(timing)
    return cfg


def _cfg_turning(**turning):
    """BASE_CFG with a turning block."""
    cfg = copy.deepcopy(BASE_CFG)
    cfg["turning"] = turning
    return cfg


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


class TestSaturationFlowConfig:
    def test_defaults_to_1800_when_key_absent(self):
        """Configs predating the key keep the original hard-coded value."""
        assert "saturation_flow" not in BASE_CFG["timing"]
        assert Intersection(BASE_CFG).saturation_flow == 1800.0

    def test_value_read_from_config(self):
        inter = Intersection(_cfg_with(saturation_flow=3600))
        assert inter.saturation_flow == 3600.0

    def test_value_reaches_every_approach(self):
        inter = Intersection(_cfg_with(saturation_flow=900))
        for name in ("north", "south", "east", "west"):
            assert inter.approaches[name].saturation_flow == 900.0

    def test_higher_saturation_flow_discharges_faster(self):
        """Same green time, double the flow -> more vehicles served."""
        slow = Intersection(_cfg_with(saturation_flow=900))
        fast = Intersection(_cfg_with(saturation_flow=1800))
        for inter in (slow, fast):
            inter.arrive({"north": 50, "south": 50}, 0.0)
            inter.depart_phase("NS", 10.0, 10.0)
        assert len(fast.departed_vehicles) > len(slow.departed_vehicles)

    def test_higher_saturation_flow_raises_throughput(self):
        low = _run("fixed", "balanced", duration=300.0, seed=1,
                   cfg=_cfg_with(saturation_flow=900))
        high = _run("fixed", "balanced", duration=300.0, seed=1,
                    cfg=_cfg_with(saturation_flow=1800))
        assert high.summary()["throughput"] > low.summary()["throughput"]


class TestYellowDischarge:
    def test_no_yellow_discharge_when_key_absent(self):
        assert "yellow_discharge_time" not in BASE_CFG["timing"]
        engine = SimEngine(BASE_CFG, get_algorithm("fixed", BASE_CFG))
        assert engine.yellow_discharge_time == 0.0

    def test_value_read_from_config(self):
        cfg = _cfg_with(yellow_discharge_time=2.0)
        engine = SimEngine(cfg, get_algorithm("fixed", cfg))
        assert engine.yellow_discharge_time == 2.0

    def test_clamped_to_yellow_duration(self):
        """Cannot discharge for longer than the yellow interval itself."""
        cfg = _cfg_with(yellow_duration=3, yellow_discharge_time=10.0)
        engine = SimEngine(cfg, get_algorithm("fixed", cfg))
        assert engine.yellow_discharge_time == 3.0

    def test_discharges_early_in_yellow_but_not_late(self):
        cfg = _cfg_with(yellow_discharge_time=2.0)
        engine = SimEngine(cfg, get_algorithm("fixed", cfg))
        engine.phase_manager.state = SignalState.YELLOW

        engine.phase_manager.state_elapsed = 0.5
        assert engine._is_discharging()
        engine.phase_manager.state_elapsed = 2.5
        assert not engine._is_discharging()

    def test_never_discharges_during_all_red(self):
        cfg = _cfg_with(yellow_discharge_time=2.0)
        engine = SimEngine(cfg, get_algorithm("fixed", cfg))
        engine.phase_manager.state = SignalState.ALL_RED
        engine.phase_manager.state_elapsed = 0.0
        assert not engine._is_discharging()

    def test_yellow_discharge_raises_throughput(self):
        """Extra amber discharge serves strictly more vehicles under demand."""
        without = _run("fixed", "balanced", duration=300.0, seed=3,
                       cfg=_cfg_with(yellow_discharge_time=0.0))
        with_ = _run("fixed", "balanced", duration=300.0, seed=3,
                     cfg=_cfg_with(yellow_discharge_time=2.0))
        assert with_.summary()["throughput"] > without.summary()["throughput"]


class TestQueueCapacity:
    def test_unlimited_when_key_absent(self):
        """Configs predating the key keep unbounded queues."""
        assert "queue_capacity" not in BASE_CFG["timing"]
        inter = Intersection(BASE_CFG)
        assert inter.capacity is None
        assert not inter.approaches["north"].is_full

    def test_value_read_from_config(self):
        inter = Intersection(_cfg_with(queue_capacity=25))
        assert inter.capacity == 25
        assert all(q.capacity == 25 for q in inter.approaches.values())

    def test_rejects_non_positive_capacity(self):
        with pytest.raises(ValueError):
            Intersection(_cfg_with(queue_capacity=0))

    def test_queue_never_exceeds_capacity(self):
        inter = Intersection(_cfg_with(queue_capacity=10))
        inter.arrive({"north": 50}, 0.0)
        assert inter.approaches["north"].length == 10

    def test_excess_arrivals_reported_as_blocked(self):
        inter = Intersection(_cfg_with(queue_capacity=10))
        blocked = inter.arrive({"north": 50, "south": 4}, 0.0)
        assert blocked["north"] == 40
        assert blocked["south"] == 0
        assert inter.total_blocked == 40

    def test_nothing_blocked_when_storage_unlimited(self):
        inter = Intersection(BASE_CFG)
        inter.arrive({"north": 500}, 0.0)
        assert inter.total_blocked == 0
        assert inter.approaches["north"].length == 500

    def test_space_frees_up_after_discharge(self):
        """A full approach accepts arrivals again once green has drained it."""
        inter = Intersection(_cfg_with(queue_capacity=10))
        inter.arrive({"north": 10}, 0.0)
        assert inter.arrive({"north": 5}, 1.0)["north"] == 5
        inter.depart_phase("NS", 10.0, 10.0)
        assert inter.arrive({"north": 3}, 20.0)["north"] == 0

    def test_metrics_report_blocking_under_oversaturation(self):
        """Demand far above capacity fills the approaches and spills back."""
        s = _run("fixed", "balanced", duration=300.0, seed=5,
                 cfg=_cfg_with(queue_capacity=10)).summary()
        assert s["blocked"] > 0
        assert 0.0 < s["blocked_pct"] < 100.0

    def test_no_blocking_reported_without_capacity(self):
        s = _run("fixed", "balanced", duration=300.0, seed=5).summary()
        assert s["blocked"] == 0
        assert s["blocked_pct"] == 0.0

    def test_capacity_caps_max_queue(self):
        capacity = 10
        m = _run("fixed", "balanced", duration=300.0, seed=5,
                 cfg=_cfg_with(queue_capacity=capacity))
        # max_queue is the total across all four approaches.
        assert m.summary()["max_queue"] <= capacity * 4


class TestTurningMovements:
    def test_all_through_when_block_absent(self):
        """Configs predating the turning block send every vehicle straight."""
        assert "turning" not in BASE_CFG
        inter = Intersection(BASE_CFG)
        assert inter.turning.adjustment == 1.0
        inter.arrive({"north": 20}, 0.0)
        departed = inter.depart_phase("NS", 60.0, 60.0)
        assert all(v.movement == "through" for v in departed)

    def test_shares_are_normalised(self):
        mix = Intersection(_cfg_turning(through=70, left=15, right=15)).turning
        assert mix.shares["through"] == pytest.approx(0.7)
        assert sum(mix.shares.values()) == pytest.approx(1.0)

    def test_adjustment_is_share_weighted(self):
        mix = Intersection(_cfg_turning(
            through=0.70, left=0.15, right=0.15,
            left_adjustment=0.45, right_adjustment=0.85,
        )).turning
        assert mix.adjustment == pytest.approx(0.895)

    def test_rejects_out_of_range_adjustment(self):
        with pytest.raises(ValueError):
            Intersection(_cfg_turning(through=1.0, left_adjustment=0.0))
        with pytest.raises(ValueError):
            Intersection(_cfg_turning(through=1.0, right_adjustment=1.5))

    def test_rejects_degenerate_shares(self):
        with pytest.raises(ValueError):
            Intersection(_cfg_turning(through=0.0, left=0.0, right=0.0))
        with pytest.raises(ValueError):
            Intersection(_cfg_turning(through=1.0, left=-0.5))

    def test_sampled_movements_follow_configured_shares(self):
        mix = Intersection(_cfg_turning(through=0.70, left=0.15, right=0.15)).turning
        sample = mix.sample(5000)
        share = sample.count("through") / len(sample)
        assert share == pytest.approx(0.70, abs=0.03)

    def test_same_seed_gives_same_movements(self):
        cfg = _cfg_turning(through=0.70, left=0.15, right=0.15)
        a = Intersection(cfg, seed=7).turning.sample(50)
        b = Intersection(cfg, seed=7).turning.sample(50)
        assert a == b

    def test_turning_vehicle_occupies_more_green(self):
        inter = Intersection(_cfg_turning(
            through=1.0, left_adjustment=0.45, right_adjustment=0.85,
        ))
        q = inter.approaches["north"]
        q.arrive(3, 0.0, movements=["through", "left", "right"])
        through, left, right = q._queue
        assert q.service_time(left) > q.service_time(right) > q.service_time(through)
        # A permitted left turn at 45% of saturation flow costs 1/0.45 as much.
        assert q.service_time(left) == pytest.approx(q.service_time(through) / 0.45)

    def test_turns_reduce_discharge_in_the_same_green(self):
        """Same green, same queue length — turns get fewer vehicles out."""
        cfg = _cfg_turning(through=1.0, left_adjustment=0.45)
        straight = Intersection(cfg).approaches["north"]
        turning = Intersection(cfg).approaches["north"]
        straight.arrive(30, 0.0, movements=["through"] * 30)
        turning.arrive(30, 0.0, movements=["left"] * 30)
        assert len(turning.depart(30.0, 30.0)) < len(straight.depart(30.0, 30.0))

    def test_a_left_turner_holds_up_the_queue_behind_it(self):
        """Single-lane approach: head-of-line blocking, not just a rate cut."""
        cfg = _cfg_turning(through=1.0, left_adjustment=0.45)
        q = Intersection(cfg).approaches["north"]
        # base service time = 3600/1800 = 2s; a left turn costs 2/0.45 = 4.44s
        q.arrive(2, 0.0, movements=["left", "through"])
        assert len(q.depart(4.0, 4.0)) == 0  # not even the leader has cleared
        assert len(q.depart(1.0, 5.0)) == 1  # leader clears at 4.44s
        assert len(q.depart(2.0, 7.0)) == 1  # follower needs another 2s

    def test_turns_lower_throughput_end_to_end(self):
        cfg = _cfg_turning(
            through=0.70, left=0.15, right=0.15,
            left_adjustment=0.45, right_adjustment=0.85,
        )
        no_turns = _run("fixed", "balanced", duration=600.0, seed=11)
        with_turns = _run("fixed", "balanced", duration=600.0, seed=11, cfg=cfg)
        assert with_turns.summary()["throughput"] < no_turns.summary()["throughput"]
