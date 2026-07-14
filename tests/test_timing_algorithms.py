import pytest

from src.signals.timing_algorithms import (
    FixedTimingAlgorithm,
    LongestQueueFirstAlgorithm,
    ProportionalTimingAlgorithm,
    QueueClearingAlgorithm,
    get_algorithm,
)

CFG = {
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
}


class TestFixedAlgorithm:
    def test_alternates_ns_to_ew(self):
        algo = FixedTimingAlgorithm(CFG)
        assert algo.next_phase({}, "NS", 0) == "EW"

    def test_alternates_ew_to_ns(self):
        algo = FixedTimingAlgorithm(CFG)
        assert algo.next_phase({}, "EW", 0) == "NS"

    def test_green_duration_in_bounds(self):
        algo = FixedTimingAlgorithm(CFG)
        d = algo.green_duration({}, "NS")
        assert CFG["timing"]["min_green"] <= d <= CFG["timing"]["max_green"]

    def test_green_duration_constant(self):
        algo = FixedTimingAlgorithm(CFG)
        d1 = algo.green_duration({"north": 10}, "NS")
        d2 = algo.green_duration({"north": 0}, "NS")
        assert d1 == d2

    def test_reason_not_empty(self):
        algo = FixedTimingAlgorithm(CFG)
        algo.next_phase({}, "NS", 0)
        assert algo.get_last_reason() != ""


class TestProportionalAlgorithm:
    def test_alternates(self):
        algo = ProportionalTimingAlgorithm(CFG)
        assert algo.next_phase({}, "NS", 0) == "EW"

    def test_empty_queues_returns_min_green(self):
        algo = ProportionalTimingAlgorithm(CFG)
        assert algo.green_duration({}, "NS") == CFG["timing"]["min_green"]

    def test_heavier_ns_gets_more_green(self):
        algo = ProportionalTimingAlgorithm(CFG)
        q = {"north": 20, "south": 20, "east": 0, "west": 0}
        assert algo.green_duration(q, "NS") > algo.green_duration(q, "EW")

    def test_duration_clamped_to_max(self):
        algo = ProportionalTimingAlgorithm(CFG)
        q = {"north": 1000, "south": 0, "east": 0, "west": 0}
        assert algo.green_duration(q, "NS") <= CFG["timing"]["max_green"]

    def test_duration_clamped_to_min(self):
        algo = ProportionalTimingAlgorithm(CFG)
        q = {"north": 0, "south": 0, "east": 1000, "west": 0}
        assert algo.green_duration(q, "NS") >= CFG["timing"]["min_green"]


class TestQueueClearingAlgorithm:
    def _algo(self):
        return QueueClearingAlgorithm(CFG)

    def test_short_queue_served_first_over_long(self):
        algo = self._algo()
        # NS short, EW long
        q = {"north": 2, "south": 2, "east": 10, "west": 10}
        assert algo.next_phase(q, "EW", 0) == "NS"

    def test_both_short_serves_smaller(self):
        algo = self._algo()
        q = {"north": 1, "south": 1, "east": 4, "west": 4}
        # NS=2, EW=8 — both short (<=5)? EW=8>5 so NS short, EW long → serves NS
        assert algo.next_phase(q, "EW", 0) == "NS"

    def test_both_short_equal_returns_valid_phase(self):
        algo = self._algo()
        q = {"north": 2, "south": 2, "east": 2, "west": 2}
        result = algo.next_phase(q, "EW", 0)
        assert result in ("NS", "EW")

    def test_both_long_serves_larger(self):
        algo = self._algo()
        q = {"north": 8, "south": 8, "east": 6, "west": 6}
        assert algo.next_phase(q, "EW", 0) == "NS"

    def test_aging_triggers_for_starving_phase(self):
        algo = self._algo()
        # Simulate: NS was just served (t=100), EW last served at t=0
        algo._last_served = {"NS": 100.0, "EW": 0.0}
        algo._sim_time = 100.0
        q = {"north": 0, "south": 0, "east": 1, "west": 1}
        # EW hasn't been served for 100s > threshold 60s
        assert algo.next_phase(q, "NS", 100.0) == "EW"

    def test_no_aging_within_threshold(self):
        algo = self._algo()
        algo._last_served = {"NS": 50.0, "EW": 50.0}
        algo._sim_time = 90.0
        q = {"north": 10, "south": 10, "east": 0, "west": 0}
        # Neither phase has been starving (90-50=40 < 60)
        result = algo.next_phase(q, "EW", 90.0)
        # NS has large queue, should be chosen
        assert result == "NS"

    def test_empty_queues_returns_valid_phase(self):
        algo = self._algo()
        result = algo.next_phase({}, "NS", 0)
        assert result in ("NS", "EW")

    def test_short_green_for_short_queue(self):
        algo = self._algo()
        q = {"north": 3, "south": 1, "east": 0, "west": 0}
        assert algo.green_duration(q, "NS") == CFG["queue_clearing"]["short_queue_green"]

    def test_extended_green_for_long_queue(self):
        algo = self._algo()
        q = {"north": 10, "south": 10, "east": 0, "west": 0}
        d = algo.green_duration(q, "NS")
        assert d >= CFG["queue_clearing"]["long_queue_min_green"]

    def test_extended_green_clamped_to_max(self):
        algo = self._algo()
        q = {"north": 500, "south": 500, "east": 0, "west": 0}
        assert algo.green_duration(q, "NS") <= CFG["queue_clearing"]["long_queue_max_green"]

    def test_reason_string_non_empty(self):
        algo = self._algo()
        algo.next_phase({"north": 3}, "NS", 0)
        assert len(algo.get_last_reason()) > 0


class TestLongestQueueFirstAlgorithm:
    def _algo(self):
        return LongestQueueFirstAlgorithm(CFG)

    def test_is_subclass_of_queue_clearing(self):
        # The engine dispatches aging hooks via isinstance(QueueClearingAlgorithm),
        # so LQF must remain a subclass for those hooks to fire.
        assert isinstance(self._algo(), QueueClearingAlgorithm)

    def test_serves_larger_queue_when_both_long(self):
        algo = self._algo()
        q = {"north": 6, "south": 6, "east": 10, "west": 10}
        # NS=12, EW=20 → serve EW (the larger)
        assert algo.next_phase(q, "NS", 0) == "EW"

    def test_serves_long_over_short_opposite_of_sjf(self):
        # The defining behavioural difference from queue_clearing (SJF): given the
        # same queue with NS short and EW long, SJF serves the SHORT phase and LQF
        # serves the LONG one. No aging (threshold 60, fresh algo at t=0).
        q = {"north": 4, "south": 0, "east": 10, "west": 10}  # NS=4 short, EW=20 long
        sjf = QueueClearingAlgorithm(CFG)
        lqf = LongestQueueFirstAlgorithm(CFG)
        assert sjf.next_phase(q, "EW", 0) == "NS"
        assert lqf.next_phase(q, "EW", 0) == "EW"

    def test_serves_larger_when_both_short(self):
        algo = self._algo()
        q = {"north": 4, "south": 0, "east": 1, "west": 1}  # NS=4, EW=2, both short
        assert algo.next_phase(q, "EW", 0) == "NS"

    def test_empty_phase_not_served_over_nonempty(self):
        algo = self._algo()
        q = {"north": 0, "south": 0, "east": 3, "west": 2}  # NS empty
        assert algo.next_phase(q, "NS", 0) == "EW"

    def test_both_empty_alternates(self):
        algo = self._algo()
        assert algo.next_phase({}, "NS", 0) == "EW"
        assert algo.next_phase({}, "EW", 0) == "NS"

    def test_aging_promotes_starving_phase_over_larger_queue(self):
        algo = self._algo()
        algo._last_served = {"NS": 100.0, "EW": 0.0}
        algo._sim_time = 100.0
        # NS has the bigger queue, but EW has starved (100s > 60s) → EW promoted
        q = {"north": 10, "south": 10, "east": 1, "west": 1}
        assert algo.next_phase(q, "NS", 100.0) == "EW"

    def test_inherits_green_duration_rule(self):
        algo = self._algo()
        short = {"north": 3, "south": 1, "east": 0, "west": 0}
        long = {"north": 10, "south": 10, "east": 0, "west": 0}
        assert algo.green_duration(short, "NS") == CFG["queue_clearing"]["short_queue_green"]
        assert algo.green_duration(long, "NS") >= CFG["queue_clearing"]["long_queue_min_green"]

    def test_reason_mentions_longest(self):
        algo = self._algo()
        algo.next_phase({"north": 6, "south": 6, "east": 10, "west": 10}, "NS", 0)
        assert "Longest" in algo.get_last_reason()


class TestGetAlgorithm:
    def test_all_names_resolve(self):
        for name in ("fixed", "proportional", "queue_clearing", "longest_queue_first"):
            algo = get_algorithm(name, CFG)
            assert algo is not None

    def test_hyphenated_name(self):
        algo = get_algorithm("queue-clearing", CFG)
        assert isinstance(algo, QueueClearingAlgorithm)

    def test_invalid_raises_value_error(self):
        with pytest.raises(ValueError):
            get_algorithm("nonexistent", CFG)

    def test_algorithms_return_valid_phase_ids(self):
        for name in ("fixed", "proportional", "queue_clearing", "longest_queue_first"):
            algo = get_algorithm(name, CFG)
            phase = algo.next_phase({}, "NS", 0)
            assert phase in ("NS", "EW"), f"{name} returned invalid phase {phase!r}"
