"""
Tests for emergency-vehicle priority: the queue model, the preemption
controller, the signal sequence it drives, the vision classifier, and — most
importantly — the invariant that a config with no `emergency:` block behaves
exactly as it did before preemption existed.
"""
import copy

import numpy as np
import pytest

from src.detection.detector import Detection
from src.detection.emergency_classifier import EmergencyClassifier
from src.detection.roi_manager import ROIManager
from src.metrics.collector import MetricsCollector
from src.signals.phase_manager import PhaseManager, SignalState
from src.signals.timing_algorithms import (
    EmergencyPreemptionController,
    build_controller,
    emergency_enabled,
    get_algorithm,
)
from src.simulation.intersection import ApproachQueue, Intersection
from src.simulation.sim_engine import SimEngine
from src.simulation.traffic_generator import TrafficGenerator

BASE_CFG = {
    "timing": {
        "min_green": 10,
        "max_green": 60,
        "yellow_duration": 3,
        "all_red_duration": 2,
        "startup_lost_time": 2.0,
        "headway": 2.0,
        "max_wait_threshold": 20,
        "saturation_flow": 1800,
        "yellow_discharge_time": 2.0,
        "queue_capacity": 25,
    },
    "queue_clearing": {
        "short_queue_threshold": 5,
        "short_queue_green": 15,
        "long_queue_min_green": 20,
        "long_queue_max_green": 60,
    },
    "scenarios": {
        "balanced": {"north": 0.09, "south": 0.09, "east": 0.09, "west": 0.09},
    },
}

EMERGENCY_CFG = {
    "enabled": True,
    "arrival_rate": 0.01,
    "min_green_before_preempt": 5.0,
    "max_preempt_green": 45.0,
    "clearance_extension": 3.0,
}


def cfg_with_emergency(**overrides) -> dict:
    c = copy.deepcopy(BASE_CFG)
    c["emergency"] = {**EMERGENCY_CFG, **overrides}
    return c


def cfg_without_emergency() -> dict:
    return copy.deepcopy(BASE_CFG)


# ---------------------------------------------------------------------------
# The invariant: no `emergency:` block == the model as it was before.
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_absent_block_means_disabled(self):
        assert emergency_enabled(cfg_without_emergency()) is False

    def test_explicit_false_means_disabled(self):
        assert emergency_enabled(cfg_with_emergency(enabled=False)) is False

    def test_build_controller_does_not_wrap_when_absent(self):
        algo = build_controller("queue_clearing", cfg_without_emergency())
        assert not isinstance(algo, EmergencyPreemptionController)

    def test_build_controller_wraps_when_enabled(self):
        algo = build_controller("queue_clearing", cfg_with_emergency())
        assert isinstance(algo, EmergencyPreemptionController)

    def test_no_emergency_vehicles_are_generated_when_absent(self):
        gen = TrafficGenerator(cfg_without_emergency(), "balanced", seed=1)
        for _ in range(20_000):
            assert gen.emergency_arrivals(0.1) == []

    def test_disabled_run_is_bit_identical_to_pre_emergency_model(self):
        """
        The headline guarantee: turning the feature off reproduces the old
        numbers exactly, not approximately.
        """
        results = []
        for cfg in (cfg_without_emergency(), cfg_with_emergency(enabled=False)):
            algo = build_controller("longest_queue_first", cfg)
            results.append(SimEngine(cfg, algo, "balanced", seed=7).run(300).summary())
        assert results[0] == results[1]
        assert results[0]["ev_served"] == 0
        assert results[0]["preemptions"] == 0

    def test_enabling_does_not_perturb_the_ordinary_arrival_stream(self):
        """
        EVs are drawn from their own RNG, so enabling preemption must not shift
        the Poisson sequence of ordinary vehicles.
        """
        plain = TrafficGenerator(cfg_without_emergency(), "balanced", seed=3)
        with_ev = TrafficGenerator(cfg_with_emergency(), "balanced", seed=3)
        for _ in range(5_000):
            with_ev.emergency_arrivals(0.1)   # consumes only the EV stream
            assert plain.arrivals_all(0.1) == with_ev.arrivals_all(0.1)

    def test_summary_keys_are_zero_not_missing_when_disabled(self):
        s = MetricsCollector().summary()
        assert s["ev_served"] == 0
        assert s["avg_ev_wait"] == 0.0
        assert s["max_ev_wait"] == 0.0
        assert s["preemptions"] == 0


# ---------------------------------------------------------------------------
# Queue model
# ---------------------------------------------------------------------------

class TestEmergencyQueueing:
    def test_emergency_vehicle_goes_to_the_head_of_the_queue(self):
        q = ApproachQueue("north")
        q.arrive(5, 0.0)
        ev = q.arrive_emergency(1.0)
        assert q._queue[0] is ev
        assert q.length == 6

    def test_emergency_vehicles_keep_fifo_order_among_themselves(self):
        q = ApproachQueue("north")
        q.arrive(2, 0.0)
        first = q.arrive_emergency(1.0)
        second = q.arrive_emergency(2.0)
        assert q._queue[0] is first
        assert q._queue[1] is second

    def test_emergency_vehicle_ignores_queue_capacity(self):
        q = ApproachQueue("north", capacity=3)
        assert q.arrive(5, 0.0) == 2          # 2 ordinary vehicles blocked
        assert q.is_full
        ev = q.arrive_emergency(1.0)
        assert q._queue[0] is ev
        assert q.length == 4                  # accepted despite being full
        assert q.blocked == 2                 # and not counted as blocked

    def test_has_emergency_clears_once_it_departs(self):
        q = ApproachQueue("north", saturation_flow=3600.0)
        q.arrive_emergency(0.0)
        assert q.has_emergency
        q.depart(5.0, 5.0)
        assert not q.has_emergency

    def test_intersection_reports_emergency_phases(self):
        inter = Intersection(BASE_CFG)
        assert inter.emergency_phases() == set()
        inter.arrive_emergency(["east"], 0.0)
        assert inter.emergency_approaches() == {"east"}
        assert inter.emergency_phases() == {"EW"}
        inter.arrive_emergency(["north"], 0.0)
        assert inter.emergency_phases() == {"NS", "EW"}

    def test_emergency_vehicle_is_a_through_movement(self):
        q = ApproachQueue("north", movement_factors={"through": 1.0, "left": 0.45})
        ev = q.arrive_emergency(0.0)
        assert ev.movement == "through"
        assert ev.is_emergency


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class TestEmergencyGeneration:
    def test_rate_is_approximately_honoured(self):
        cfg = cfg_with_emergency(arrival_rate=0.01)
        gen = TrafficGenerator(cfg, "balanced", seed=11)
        seconds, dt = 20_000, 0.1
        count = sum(len(gen.emergency_arrivals(dt)) for _ in range(int(seconds / dt)))
        expected = 0.01 * seconds * 4          # four approaches
        assert expected * 0.9 < count < expected * 1.1

    def test_zero_rate_generates_nothing(self):
        gen = TrafficGenerator(cfg_with_emergency(arrival_rate=0.0), "balanced", seed=1)
        assert all(gen.emergency_arrivals(0.1) == [] for _ in range(1000))

    def test_negative_rate_is_rejected(self):
        with pytest.raises(ValueError, match="must not be negative"):
            TrafficGenerator(cfg_with_emergency(arrival_rate=-1.0), "balanced")


# ---------------------------------------------------------------------------
# The preemption controller
# ---------------------------------------------------------------------------

class TestPreemptionController:
    def _controller(self, base="fixed", **overrides):
        cfg = cfg_with_emergency(**overrides)
        return EmergencyPreemptionController(get_algorithm(base, cfg), cfg)

    def test_passes_through_when_no_emergency(self):
        c = self._controller("queue_clearing")
        c.notify_emergency(set(), "NS")
        assert not c.is_preempting
        # Same decision the bare controller would make.
        bare = get_algorithm("queue_clearing", cfg_with_emergency())
        queues = {"north": 8, "south": 8, "east": 2, "west": 2}
        assert c.next_phase(queues, "NS", 0.0) == bare.next_phase(queues, "NS", 0.0)

    def test_preempts_to_the_phase_with_the_emergency_vehicle(self):
        c = self._controller("fixed")
        started = c.notify_emergency({"EW"}, "NS")
        assert started is True
        assert c.is_preempting and c.target_phase == "EW"
        # Overrides the base controller's alternation entirely.
        assert c.next_phase({}, "EW", 0.0) == "EW"
        assert c.next_phase({}, "NS", 0.0) == "EW"

    def test_preemption_overrides_a_starving_phase(self):
        """Aging is the strongest rule in the base controller — EVP still wins."""
        c = self._controller("longest_queue_first")
        c.update_sim_time(1000.0)             # NS has starved for ages
        c.notify_emergency({"EW"}, "EW")
        assert c.next_phase({"north": 30, "south": 30}, "EW", 0.0) == "EW"

    def test_green_duration_is_the_preempt_cap_for_the_target(self):
        c = self._controller("fixed", max_preempt_green=42.0)
        c.notify_emergency({"NS"}, "NS")
        assert c.green_duration({}, "NS") == 42.0
        # The non-target phase still gets whatever the base says.
        assert c.green_duration({}, "EW") == get_algorithm(
            "fixed", cfg_with_emergency()
        ).green_duration({}, "EW")

    def test_started_flag_is_only_true_on_the_rising_edge(self):
        c = self._controller()
        assert c.notify_emergency({"NS"}, "EW") is True
        assert c.notify_emergency({"NS"}, "NS") is False
        assert c.preemption_count == 1

    def test_serving_phase_wins_when_both_have_an_emergency_vehicle(self):
        c = self._controller()
        c.notify_emergency({"NS", "EW"}, "EW")
        assert c.target_phase == "EW"

    def test_release_waits_for_the_clearance_extension(self):
        c = self._controller(clearance_extension=3.0)
        c.update_sim_time(100.0)
        c.notify_emergency({"NS"}, "NS")
        assert c.is_preempting

        # EV departs at t=101, so the hold runs to t=104.
        c.update_sim_time(101.0)
        c.notify_emergency(set(), "NS")
        assert c.is_preempting, "must hold through the clearance extension"

        c.update_sim_time(103.9)
        c.notify_emergency(set(), "NS")
        assert c.is_preempting, "extension must not end early"

        c.update_sim_time(104.0)
        c.notify_emergency(set(), "NS")
        assert not c.is_preempting

    def test_a_new_emergency_cancels_a_pending_release(self):
        c = self._controller(clearance_extension=3.0)
        c.update_sim_time(100.0)
        c.notify_emergency({"NS"}, "NS")
        c.update_sim_time(101.0)
        c.notify_emergency(set(), "NS")       # release timer starts
        c.notify_emergency({"NS"}, "NS")      # another EV arrives
        c.update_sim_time(110.0)
        c.notify_emergency({"NS"}, "NS")
        assert c.is_preempting

    def test_delegates_optional_hooks_to_the_base(self):
        cfg = cfg_with_emergency()
        base = get_algorithm("queue_clearing", cfg)
        c = EmergencyPreemptionController(base, cfg)
        c.update_sim_time(55.0)
        c.record_served("EW")
        assert base._sim_time == 55.0
        assert base._last_served["EW"] == 55.0

    def test_reason_reports_preemption_then_falls_back_to_base(self):
        c = self._controller("queue_clearing")
        c.notify_emergency({"EW"}, "NS")
        assert "PREEMPT" in c.get_last_reason()

        c.notify_emergency(set(), "NS")       # starts the clearance hold
        c.update_sim_time(999.0)
        c.notify_emergency(set(), "NS")       # hold expires, preemption released
        assert not c.is_preempting
        c.next_phase({"north": 1, "south": 1, "east": 9, "west": 9}, "NS", 0.0)
        assert "PREEMPT" not in c.get_last_reason()

    @pytest.mark.parametrize("bad", [
        {"max_preempt_green": 0},
        {"min_green_before_preempt": -1},
        {"clearance_extension": -1},
    ])
    def test_invalid_timings_are_rejected(self, bad):
        cfg = cfg_with_emergency(**bad)
        with pytest.raises(ValueError):
            EmergencyPreemptionController(get_algorithm("fixed", cfg), cfg)


# ---------------------------------------------------------------------------
# Signal sequence
# ---------------------------------------------------------------------------

class TestGreenTruncation:
    def _pm(self) -> PhaseManager:
        pm = PhaseManager(BASE_CFG, "NS")
        pm.set_green_duration(40.0)
        return pm

    def test_truncate_ends_green_at_the_safety_floor(self):
        pm = self._pm()
        pm.step(2.0)
        assert pm.truncate_green(5.0) is True
        assert pm.green_duration == 5.0
        pm.step(3.0)
        assert pm.state == SignalState.YELLOW

    def test_truncate_cannot_end_a_green_already_past_the_floor(self):
        pm = self._pm()
        pm.step(8.0)
        pm.truncate_green(5.0)
        # Ends now (8s served), not retroactively at 5s.
        assert pm.green_duration == pytest.approx(8.0)

    def test_truncate_never_extends_a_shorter_green(self):
        pm = PhaseManager(BASE_CFG, "NS")
        pm.set_green_duration(4.0)
        assert pm.truncate_green(10.0) is False
        assert pm.green_duration == 4.0

    def test_truncate_is_a_noop_outside_green(self):
        pm = self._pm()
        pm.step(41.0)
        assert pm.state == SignalState.YELLOW
        assert pm.truncate_green(0.0) is False

    def test_yellow_and_all_red_still_run_in_full_after_truncation(self):
        """Preemption shortens the wait, never the clearance intervals."""
        pm = self._pm()
        pm.step(6.0)
        pm.truncate_green(5.0)
        pm.request_phase_change("EW", 30.0)
        pm.step(0.1)
        assert pm.state == SignalState.YELLOW

        elapsed = 0.0
        while pm.state == SignalState.YELLOW:
            pm.step(0.1)
            elapsed += 0.1
        assert elapsed == pytest.approx(BASE_CFG["timing"]["yellow_duration"], abs=0.15)

        elapsed = 0.0
        while pm.state == SignalState.ALL_RED:
            pm.step(0.1)
            elapsed += 0.1
        assert elapsed == pytest.approx(BASE_CFG["timing"]["all_red_duration"], abs=0.15)
        assert pm.current_phase == "EW"

    def test_hold_green_extends_but_never_shortens(self):
        pm = self._pm()
        pm.hold_green(50.0)
        assert pm.green_duration == 50.0
        pm.hold_green(20.0)
        assert pm.green_duration == 50.0


# ---------------------------------------------------------------------------
# End-to-end through the engine
# ---------------------------------------------------------------------------

class TestEnginePreemption:
    def test_engine_serves_an_injected_emergency_vehicle_promptly(self):
        cfg = cfg_with_emergency(arrival_rate=0.0)   # inject manually
        algo = build_controller("fixed", cfg)
        eng = SimEngine(cfg, algo, "balanced", seed=5)

        # Run until EW is green, then put an ambulance on the conflicting phase.
        while not (eng.phase_manager.current_phase == "EW"
                   and eng.phase_manager.state == SignalState.GREEN):
            eng.step()
        eng.intersection.arrive_emergency(["north"], eng.t)
        arrival = eng.t

        while eng.metrics.emergency_records == [] and eng.t - arrival < 120:
            eng.step()

        assert len(eng.metrics.emergency_records) == 1
        record = eng.metrics.emergency_records[0]
        assert record.approach == "north"
        # Must beat a full cycle of the fixed controller it was wrapped around.
        assert record.wait < 30.0
        assert len(eng.metrics.preemptions) == 1
        assert eng.metrics.preemptions[0].phase == "NS"

    def test_emergency_vehicles_beat_ordinary_traffic_on_average(self):
        cfg = cfg_with_emergency(arrival_rate=0.01)
        algo = build_controller("longest_queue_first", cfg)
        summary = SimEngine(cfg, algo, "balanced", seed=3).run(1800).summary()
        assert summary["ev_served"] > 5
        assert summary["preemptions"] > 0
        assert summary["avg_ev_wait"] < summary["avg_wait"]

    def test_emergency_vehicles_count_towards_throughput_too(self):
        cfg = cfg_with_emergency(arrival_rate=0.02)
        eng = SimEngine(cfg, build_controller("fixed", cfg), "balanced", seed=9)
        m = eng.run(600)
        assert m.summary()["ev_served"] > 0
        assert len(m.vehicle_waits) >= len(m.emergency_records)

    def test_state_exposes_emergency_information(self):
        cfg = cfg_with_emergency(arrival_rate=0.0)
        eng = SimEngine(cfg, build_controller("fixed", cfg), "balanced", seed=1)
        assert eng.get_state()["preempting"] is False
        eng.intersection.arrive_emergency(["west"], 0.0)
        eng.step()
        state = eng.get_state()
        assert state["emergency_approaches"] == ["west"]
        assert state["preempting"] is True

    def test_min_green_floor_is_respected_before_truncation(self):
        cfg = cfg_with_emergency(arrival_rate=0.0, min_green_before_preempt=8.0)
        eng = SimEngine(cfg, build_controller("fixed", cfg), "balanced", seed=2)
        while not (eng.phase_manager.current_phase == "NS"
                   and eng.phase_manager.state == SignalState.GREEN
                   and eng.phase_manager.state_elapsed < 0.5):
            eng.step()
        eng.intersection.arrive_emergency(["east"], eng.t)
        eng.step()
        # Preemption is active but the conflicting green must still run 8s.
        assert eng.preemption.is_preempting
        assert eng.phase_manager.green_duration >= 8.0


# ---------------------------------------------------------------------------
# Vision: emergency classification
# ---------------------------------------------------------------------------

def _vehicle_patch(colour, size=(40, 40)) -> np.ndarray:
    frame = np.zeros((80, 80, 3), dtype=np.uint8)
    frame[20:20 + size[0], 20:20 + size[1]] = colour
    return frame


def _box() -> Detection:
    return Detection(x1=20, y1=20, x2=60, y2=60, confidence=1.0,
                     class_id=2, class_name="car")


class TestEmergencyClassifier:
    def setup_method(self):
        self.clf = EmergencyClassifier(min_lightbar_fraction=0.015, band=1.0)

    def test_flags_a_vehicle_with_a_red_and_blue_light_bar(self):
        frame = _vehicle_patch((40, 235, 190))       # fluorescent body
        frame[26:34, 22:40] = (40, 40, 240)          # red half
        frame[26:34, 40:58] = (240, 70, 40)          # blue half
        assert self.clf.is_emergency(frame, _box()) is True

    def test_plain_red_vehicle_is_not_an_emergency_vehicle(self):
        assert self.clf.is_emergency(_vehicle_patch((40, 40, 240)), _box()) is False

    def test_plain_blue_vehicle_is_not_an_emergency_vehicle(self):
        assert self.clf.is_emergency(_vehicle_patch((240, 70, 40)), _box()) is False

    def test_blue_car_with_red_tail_lights_is_not_flagged(self):
        """
        Regression: the first version of this classifier only asked whether red
        and blue were both present, and flagged every blue car on the east
        approach of the synthetic video. The balance test is what fixes it —
        the body dwarfs the tail lights.
        """
        frame = _vehicle_patch((240, 70, 40))       # blue bodywork
        frame[22:26, 24:30] = (40, 40, 240)         # small red tail lights
        frame[22:26, 50:56] = (40, 40, 240)
        assert self.clf.is_emergency(frame, _box()) is False

    def test_bus_with_blue_glazing_and_tail_lights_is_not_flagged(self):
        """
        Regression #2, found when the synthetic vehicles were redesigned. A bus
        has a long run of side glazing; when that glass was tinted blue it
        paired with the red tail-light bar to give a balance of 0.37 — just
        over the threshold — and buses started reading as ambulances. The fixes
        were green-tinted glass and corner tail lights instead of a full-width
        bar. This pins the shape of the failure, not the specific colours.
        """
        frame = np.zeros((80, 80, 3), dtype=np.uint8)
        frame[20:60, 20:60] = (60, 200, 70)          # green bus body
        frame[24:56, 22:26] = (105, 88, 60)          # blue-tinted side glazing
        frame[24:56, 54:58] = (105, 88, 60)
        frame[56:59, 22:58] = (40, 40, 200)          # full-width red tail bar
        assert self.clf.is_emergency(frame, _box()) is False

    def test_red_car_with_blue_trim_is_not_flagged(self):
        frame = _vehicle_patch((40, 40, 240))       # red bodywork
        frame[22:26, 24:32] = (240, 70, 40)         # small blue trim
        assert self.clf.is_emergency(frame, _box()) is False

    def test_adjacency_alone_would_not_have_saved_it(self):
        """
        The tail lights sit directly against the bodywork, so 'are the colours
        adjacent?' cannot separate these two cases — only their relative area
        can. This pins why the balance test is the one that matters.
        """
        car = _vehicle_patch((240, 70, 40))
        car[22:26, 24:30] = (40, 40, 240)           # red touching blue body

        ambulance = _vehicle_patch((40, 235, 190))
        ambulance[26:34, 22:40] = (40, 40, 240)     # red half of the bar
        ambulance[26:34, 40:58] = (240, 70, 40)     # blue half, also touching

        assert self.clf.is_emergency(car, _box()) is False
        assert self.clf.is_emergency(ambulance, _box()) is True

    def test_balance_threshold_is_what_separates_them(self):
        """
        Both colours clear the presence floor, so only the balance test can
        reject this — 144 red pixels against 32 blue is a ratio of 0.22.
        """
        frame = _vehicle_patch((40, 235, 190))
        frame[26:34, 22:40] = (40, 40, 240)         # 144 px of red
        frame[26:30, 42:50] = (240, 70, 40)         # 32 px of blue
        assert EmergencyClassifier(min_balance=0.35).is_emergency(frame, _box()) is False
        assert EmergencyClassifier(min_balance=0.02).is_emergency(frame, _box()) is True

    def test_colour_covering_most_of_the_vehicle_is_treated_as_paintwork(self):
        frame = _vehicle_patch((40, 40, 240))       # red body, most of the box
        frame[20:60, 20:38] = (240, 70, 40)         # and half of it blue
        # Balanced, but both are far too large to be a light bar.
        assert self.clf.is_emergency(frame, _box()) is False

    def test_desaturated_red_and_blue_do_not_trigger(self):
        """A washed-out livery is below the saturation floor, so it is ignored."""
        frame = _vehicle_patch((160, 160, 160))
        frame[26:34, 22:40] = (150, 150, 175)
        frame[26:34, 40:58] = (175, 150, 150)
        assert self.clf.is_emergency(frame, _box()) is False

    def test_a_speck_of_each_colour_is_below_the_fraction_threshold(self):
        frame = _vehicle_patch((40, 235, 190))
        frame[26:27, 22:23] = (40, 40, 240)
        frame[26:27, 24:25] = (240, 70, 40)
        assert self.clf.is_emergency(frame, _box()) is False

    def test_band_restricts_the_search_to_the_roof_line(self):
        frame = _vehicle_patch((40, 235, 190))
        frame[50:58, 22:40] = (40, 40, 240)          # bar low in the box
        frame[50:58, 40:58] = (240, 70, 40)
        assert EmergencyClassifier(band=1.0).is_emergency(frame, _box()) is True
        assert EmergencyClassifier(band=0.4).is_emergency(frame, _box()) is False

    def test_classify_sets_the_flag_and_renames_the_class(self):
        frame = _vehicle_patch((40, 235, 190))
        frame[26:34, 22:40] = (40, 40, 240)
        frame[26:34, 40:58] = (240, 70, 40)
        dets = self.clf.classify(frame, [_box()])
        assert dets[0].is_emergency is True
        assert dets[0].class_name == "emergency"

    def test_detection_defaults_to_not_emergency(self):
        assert _box().is_emergency is False

    def test_out_of_frame_box_is_handled(self):
        det = Detection(x1=-50, y1=-50, x2=-10, y2=-10, confidence=1.0,
                        class_id=2, class_name="car")
        assert self.clf.is_emergency(_vehicle_patch((40, 235, 190)), det) is False

    @pytest.mark.parametrize("bad", [
        {"band": 0.0},
        {"band": 1.5},
        {"min_lightbar_fraction": -0.1},
        {"min_balance": 0.0},
        {"min_balance": 1.5},
        {"max_lightbar_fraction": 1.5},
        # max must sit above min, or nothing can ever be classified.
        {"min_lightbar_fraction": 0.4, "max_lightbar_fraction": 0.2},
    ])
    def test_invalid_parameters_are_rejected(self, bad):
        with pytest.raises(ValueError):
            EmergencyClassifier(**bad)

    def test_thresholds_are_read_from_config(self):
        clf = EmergencyClassifier.from_config({"detection": {
            "emergency_min_lightbar_fraction": 0.05,
            "emergency_max_lightbar_fraction": 0.5,
            "emergency_min_lightbar_balance": 0.6,
            "emergency_min_saturation": 100,
            "emergency_min_value": 110,
            "emergency_lightbar_band": 0.7,
        }})
        assert clf.min_lightbar_fraction == 0.05
        assert clf.max_lightbar_fraction == 0.5
        assert clf.min_balance == 0.6
        assert clf.min_saturation == 100
        assert clf.min_value == 110
        assert clf.band == 0.7

    def test_config_defaults_apply_when_keys_are_absent(self):
        clf = EmergencyClassifier.from_config({})
        assert clf.min_lightbar_fraction == 0.015
        assert clf.band == 1.0


class TestROIEmergencyLookup:
    def _mgr(self) -> ROIManager:
        mgr = ROIManager()
        mgr.add_roi("lane_n", "north", [(0, 0), (50, 0), (50, 50), (0, 50)])
        mgr.add_roi("lane_e", "east", [(50, 0), (100, 0), (100, 50), (50, 50)])
        return mgr

    def test_locates_the_approach_of_an_emergency_detection(self):
        det = Detection(x1=60, y1=10, x2=80, y2=30, confidence=1.0,
                        class_id=2, class_name="emergency", is_emergency=True)
        assert self._mgr().emergency_approaches([det]) == {"east"}

    def test_ignores_ordinary_vehicles(self):
        det = Detection(x1=60, y1=10, x2=80, y2=30, confidence=1.0,
                        class_id=2, class_name="car")
        assert self._mgr().emergency_approaches([det]) == set()

    def test_empty_when_nothing_is_detected(self):
        assert self._mgr().emergency_approaches([]) == set()


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class TestEmergencyMetrics:
    def test_records_clearance_and_summarises_response_time(self):
        m = MetricsCollector()
        q = ApproachQueue("north", saturation_flow=3600.0)
        ev = q.arrive_emergency(0.0)
        ev.departure_time = 6.0
        m.record_emergency_clearance(ev)
        m.record_preemption(1.0, "NS")

        s = m.summary()
        assert s["ev_served"] == 1
        assert s["avg_ev_wait"] == pytest.approx(6.0)
        assert s["max_ev_wait"] == pytest.approx(6.0)
        assert s["preemptions"] == 1

    def test_emergency_csv_written_only_when_evs_ran(self, tmp_path):
        m = MetricsCollector()
        m.record_queue_snapshot(0.0, {"north": 0})
        assert "emergency" not in m.export_csv(str(tmp_path), "no_ev")

        q = ApproachQueue("north")
        ev = q.arrive_emergency(0.0)
        ev.departure_time = 4.0
        m.record_emergency_clearance(ev)
        paths = m.export_csv(str(tmp_path), "with_ev")
        assert "emergency" in paths
        assert "wait" in open(paths["emergency"]).read()
