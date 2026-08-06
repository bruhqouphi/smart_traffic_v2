"""
Tests for preemptive scheduling — the SRTF counterpart to the non-preemptive
controllers, which re-runs the selection rule mid-green instead of only at
phase boundaries.

As with the emergency tier, the invariant that matters most is that leaving it
disabled reproduces the existing results exactly.
"""
import copy

import pytest

from src.metrics.collector import MetricsCollector
from src.signals.phase_manager import SignalState
from src.signals.timing_algorithms import (
    EmergencyPreemptionController,
    PreemptiveSchedulingController,
    build_controller,
    get_algorithm,
    preemptive_enabled,
)
from src.simulation.sim_engine import SimEngine

BASE_CFG = {
    "timing": {
        "min_green": 10, "max_green": 60,
        "yellow_duration": 3, "all_red_duration": 2,
        "startup_lost_time": 2.0, "headway": 2.0,
        "max_wait_threshold": 20,
        "saturation_flow": 1800, "yellow_discharge_time": 2.0,
        "queue_capacity": 25,
    },
    "queue_clearing": {
        "short_queue_threshold": 5, "short_queue_green": 15,
        "long_queue_min_green": 20, "long_queue_max_green": 60,
    },
    "scenarios": {
        "balanced": {"north": 0.09, "south": 0.09, "east": 0.09, "west": 0.09},
    },
}

PREEMPTIVE_CFG = {
    "enabled": True,
    "min_service_before_preempt": 5.0,
    "margin_vehicles": 0,
}


def cfg(preemptive=None, emergency=None) -> dict:
    c = copy.deepcopy(BASE_CFG)
    if preemptive is not None:
        c["preemptive"] = {**PREEMPTIVE_CFG, **preemptive}
    if emergency is not None:
        c["emergency"] = {
            "enabled": True, "arrival_rate": 0.0,
            "min_green_before_preempt": 5.0, "max_preempt_green": 45.0,
            "clearance_extension": 3.0, **emergency,
        }
    return c


# ---------------------------------------------------------------------------
# Off by default
# ---------------------------------------------------------------------------

class TestDisabledByDefault:
    def test_absent_block_means_disabled(self):
        assert preemptive_enabled(cfg()) is False

    def test_explicit_false_means_disabled(self):
        assert preemptive_enabled(cfg(preemptive={"enabled": False})) is False

    def test_controller_is_not_wrapped_when_absent(self):
        algo = build_controller("longest_queue_first", cfg())
        assert not isinstance(algo, PreemptiveSchedulingController)

    def test_controller_is_wrapped_when_enabled(self):
        algo = build_controller("longest_queue_first", cfg(preemptive={}))
        assert isinstance(algo, PreemptiveSchedulingController)

    @pytest.mark.parametrize("name", ["fixed", "proportional",
                                      "queue_clearing", "longest_queue_first"])
    def test_bare_controllers_never_ask_to_preempt(self, name):
        """Every controller is non-preemptive unless explicitly wrapped."""
        algo = get_algorithm(name, cfg())
        queues = {"north": 20, "south": 20, "east": 0, "west": 0}
        assert algo.wants_preemption(queues, "EW", 999.0) is None

    def test_disabled_run_is_bit_identical(self):
        results = []
        for c in (cfg(), cfg(preemptive={"enabled": False})):
            algo = build_controller("longest_queue_first", c)
            results.append(SimEngine(c, algo, "balanced", seed=5).run(300).summary())
        assert results[0] == results[1]
        assert results[0]["sched_preemptions"] == 0


# ---------------------------------------------------------------------------
# The controller itself
# ---------------------------------------------------------------------------

class TestPreemptiveController:
    def _wrap(self, base="longest_queue_first", **overrides):
        c = cfg(preemptive=overrides)
        return PreemptiveSchedulingController(get_algorithm(base, c), c)

    def test_holds_off_until_the_minimum_service_time(self):
        p = self._wrap(min_service_before_preempt=5.0)
        queues = {"north": 0, "south": 0, "east": 12, "west": 12}
        assert p.wants_preemption(queues, "NS", 4.9) is None
        assert p.wants_preemption(queues, "NS", 5.0) == "EW"

    def test_no_preemption_when_the_rule_still_prefers_this_phase(self):
        p = self._wrap()
        queues = {"north": 12, "south": 12, "east": 1, "west": 1}
        assert p.wants_preemption(queues, "NS", 30.0) is None

    def test_margin_requires_a_real_improvement(self):
        queues = {"north": 5, "south": 5, "east": 6, "west": 6}   # EW ahead by 2
        assert self._wrap(margin_vehicles=0).wants_preemption(queues, "NS", 30.0) == "EW"
        assert self._wrap(margin_vehicles=2).wants_preemption(queues, "NS", 30.0) == "EW"
        assert self._wrap(margin_vehicles=3).wants_preemption(queues, "NS", 30.0) is None

    def test_counts_its_own_preemptions(self):
        p = self._wrap()
        queues = {"north": 0, "south": 0, "east": 9, "west": 9}
        p.wants_preemption(queues, "NS", 30.0)
        p.wants_preemption(queues, "NS", 31.0)
        assert p.preemption_count == 2

    def test_delegates_everything_else_to_the_base(self):
        c = cfg(preemptive={})
        base = get_algorithm("queue_clearing", c)
        p = PreemptiveSchedulingController(base, c)
        p.update_sim_time(42.0)
        p.record_served("EW")
        assert base._sim_time == 42.0
        assert base._last_served["EW"] == 42.0
        queues = {"north": 3, "south": 3, "east": 9, "west": 9}
        assert p.green_duration(queues, "NS") == base.green_duration(queues, "NS")
        assert p.get_last_reason() == base.get_last_reason()

    @pytest.mark.parametrize("bad", [
        {"min_service_before_preempt": -1.0},
        {"margin_vehicles": -1},
    ])
    def test_invalid_settings_are_rejected(self, bad):
        c = cfg(preemptive=bad)
        with pytest.raises(ValueError):
            PreemptiveSchedulingController(get_algorithm("fixed", c), c)


# ---------------------------------------------------------------------------
# Composition with the emergency tier
# ---------------------------------------------------------------------------

class TestPriorityOrder:
    def test_emergency_wraps_outermost(self):
        algo = build_controller("longest_queue_first",
                                cfg(preemptive={}, emergency={}))
        assert isinstance(algo, EmergencyPreemptionController)
        assert isinstance(algo.base, PreemptiveSchedulingController)

    def test_scheduler_cannot_preempt_an_emergency_vehicle(self):
        """Priority scheduling outranks the ordinary-traffic scheduler."""
        c = cfg(preemptive={}, emergency={})
        algo = build_controller("longest_queue_first", c)
        queues = {"north": 0, "south": 0, "east": 20, "west": 20}
        # Without an EV the scheduler would switch to EW immediately.
        assert algo.wants_preemption(queues, "NS", 30.0) == "EW"
        # With one on NS it must not.
        algo.notify_emergency({"NS"}, "NS")
        assert algo.wants_preemption(queues, "NS", 30.0) is None

    def test_scheduler_resumes_once_the_emergency_clears(self):
        c = cfg(preemptive={}, emergency={"clearance_extension": 0.0})
        algo = build_controller("longest_queue_first", c)
        queues = {"north": 0, "south": 0, "east": 20, "west": 20}
        algo.notify_emergency({"NS"}, "NS")
        algo.update_sim_time(100.0)
        algo.notify_emergency(set(), "NS")
        assert not algo.is_preempting
        assert algo.wants_preemption(queues, "NS", 30.0) == "EW"


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------

class TestEnginePreemptiveScheduling:
    def test_engine_records_scheduler_preemptions(self):
        c = cfg(preemptive={})
        algo = build_controller("longest_queue_first", c)
        summary = SimEngine(c, algo, "balanced", seed=3).run(600).summary()
        assert summary["sched_preemptions"] > 0

    def test_it_runs_more_cycles_than_the_non_preemptive_controller(self):
        """Cutting greens short is what raises the service rate."""
        plain = SimEngine(cfg(), build_controller("fixed", cfg()),
                          "balanced", seed=3).run(600).summary()
        c = cfg(preemptive={})
        pre = SimEngine(c, build_controller("fixed", c),
                        "balanced", seed=3).run(600).summary()
        assert pre["num_cycles"] > plain["num_cycles"]

    def test_a_high_enough_floor_degenerates_to_non_preemptive(self):
        """
        Raise the minimum service time above the cycle time and preemption can
        never fire, so the result must collapse back onto the non-preemptive
        controller exactly. This is the knob's degenerate end.
        """
        plain = SimEngine(cfg(), build_controller("longest_queue_first", cfg()),
                          "balanced", seed=11).run(600).summary()
        c = cfg(preemptive={"min_service_before_preempt": 10_000.0})
        pre = SimEngine(c, build_controller("longest_queue_first", c),
                        "balanced", seed=11).run(600).summary()
        assert pre["sched_preemptions"] == 0
        assert pre["avg_wait"] == pytest.approx(plain["avg_wait"])

    def test_min_service_floor_is_honoured_in_the_signal(self):
        c = cfg(preemptive={"min_service_before_preempt": 8.0})
        eng = SimEngine(c, build_controller("longest_queue_first", c),
                        "balanced", seed=7)
        for _ in range(6000):
            eng.step()
            pm = eng.phase_manager
            if pm.state == SignalState.GREEN:
                # A green may be cut short, but never below the floor.
                assert pm.green_duration >= 8.0 - 1e-9

    def test_summary_key_is_zero_not_missing_when_disabled(self):
        assert MetricsCollector().summary()["sched_preemptions"] == 0
