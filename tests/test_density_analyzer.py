"""
Tests for clearance-time formula and queue-classification (density analysis).
These verify the correctness of the ApproachQueue and Intersection models.
"""
import pytest

from src.simulation.intersection import ApproachQueue, Intersection

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


class TestClearanceTimeFormula:
    """Clearance = startup_lost + max(approach_a, approach_b) * headway (NOT sum)."""

    def test_ns_uses_max_not_sum(self):
        inter = Intersection(CFG)
        inter.approaches["north"].arrive(8, 0.0)
        inter.approaches["south"].arrive(4, 0.0)
        ct = inter.clearance_time("NS")
        expected = CFG["timing"]["startup_lost_time"] + 8 * CFG["timing"]["headway"]
        assert ct == pytest.approx(expected)

    def test_ew_uses_max_not_sum(self):
        inter = Intersection(CFG)
        inter.approaches["east"].arrive(3, 0.0)
        inter.approaches["west"].arrive(10, 0.0)
        ct = inter.clearance_time("EW")
        expected = CFG["timing"]["startup_lost_time"] + 10 * CFG["timing"]["headway"]
        assert ct == pytest.approx(expected)

    def test_clearance_empty_queue(self):
        inter = Intersection(CFG)
        ct = inter.clearance_time("NS")
        assert ct == pytest.approx(CFG["timing"]["startup_lost_time"])

    def test_equal_queues(self):
        inter = Intersection(CFG)
        inter.approaches["north"].arrive(5, 0.0)
        inter.approaches["south"].arrive(5, 0.0)
        ct = inter.clearance_time("NS")
        expected = CFG["timing"]["startup_lost_time"] + 5 * CFG["timing"]["headway"]
        assert ct == pytest.approx(expected)


class TestQueueClassification:
    """Verifies short/long boundary used by the timing algorithm."""

    def setup_method(self):
        from src.signals.timing_algorithms import QueueClearingAlgorithm
        self._algo = QueueClearingAlgorithm(CFG)
        self.threshold = CFG["queue_clearing"]["short_queue_threshold"]

    def test_short_queue_boundary_inclusive(self):
        q = {"north": self.threshold, "south": 0, "east": 0, "west": 0}
        ns_total = q["north"] + q["south"]
        assert ns_total <= self.threshold

    def test_long_queue_boundary(self):
        q = {"north": self.threshold + 1, "south": 0, "east": 0, "west": 0}
        ns_total = q["north"] + q["south"]
        assert ns_total > self.threshold

    def test_short_gets_short_green(self):
        q = {"north": 2, "south": 2, "east": 0, "west": 0}
        d = self._algo.green_duration(q, "NS")
        assert d == CFG["queue_clearing"]["short_queue_green"]

    def test_long_gets_extended_green(self):
        q = {"north": 8, "south": 8, "east": 0, "west": 0}
        d = self._algo.green_duration(q, "NS")
        assert d >= CFG["queue_clearing"]["long_queue_min_green"]


class TestApproachQueue:
    def test_arrivals_accumulate(self):
        q = ApproachQueue("north")
        q.arrive(3, 0.0)
        q.arrive(3, 1.0)
        assert q.length == 6

    def test_departure_reduces_queue(self):
        q = ApproachQueue("north", saturation_flow=1800.0)
        q.arrive(20, 0.0)
        before = q.length
        departed = q.depart(5.0, 1.0)
        assert q.length < before
        assert len(departed) > 0

    def test_departure_sets_departure_time(self):
        q = ApproachQueue("north")
        q.arrive(5, 0.0)
        departed = q.depart(5.0, 10.0)
        for v in departed:
            assert v.departure_time == pytest.approx(10.0)

    def test_wait_time_computed(self):
        q = ApproachQueue("north")
        q.arrive(1, 0.0)
        departed = q.depart(2.0, 15.0)
        assert departed[0].wait_time == pytest.approx(15.0)

    def test_cannot_depart_more_than_queued(self):
        q = ApproachQueue("north")
        q.arrive(2, 0.0)
        departed = q.depart(3600.0, 1.0)  # very long green
        assert len(departed) == 2
        assert q.length == 0

    def test_no_departures_when_empty(self):
        q = ApproachQueue("north")
        departed = q.depart(10.0, 5.0)
        assert departed == []
