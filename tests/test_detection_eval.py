"""Tests for the detection-accuracy scoring in src/metrics/detection_eval.py."""
import pytest

from src.metrics.detection_eval import DetectionScorer, ioa, iou, match_frame


class TestIoU:
    def test_identical_boxes_are_one(self):
        assert iou([0, 0, 10, 10], [0, 0, 10, 10]) == pytest.approx(1.0)

    def test_disjoint_boxes_are_zero(self):
        assert iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0

    def test_touching_edges_do_not_overlap(self):
        assert iou([0, 0, 10, 10], [10, 0, 20, 10]) == 0.0

    def test_half_overlap(self):
        # Union 150, intersection 50.
        assert iou([0, 0, 10, 10], [5, 0, 15, 10]) == pytest.approx(50 / 150)

    def test_degenerate_box_does_not_divide_by_zero(self):
        assert iou([0, 0, 0, 0], [0, 0, 10, 10]) == 0.0


class TestIoA:
    def test_fully_contained_box_is_one(self):
        assert ioa([2, 2, 4, 4], [0, 0, 10, 10]) == pytest.approx(1.0)

    def test_half_contained(self):
        assert ioa([0, 0, 10, 10], [5, 0, 15, 10]) == pytest.approx(0.5)

    def test_is_asymmetric_unlike_iou(self):
        small, large = [0, 0, 2, 2], [0, 0, 10, 10]
        assert ioa(small, large) == pytest.approx(1.0)
        assert ioa(large, small) == pytest.approx(0.04)


class TestMatchFrame:
    def test_perfect_match(self):
        boxes = [[0, 0, 10, 10], [20, 20, 30, 30]]
        matches, fp, fn = match_frame(boxes, boxes)
        assert len(matches) == 2
        assert fp == [] and fn == []

    def test_missed_vehicle_is_a_false_negative(self):
        matches, fp, fn = match_frame([[0, 0, 10, 10], [50, 50, 60, 60]],
                                      [[0, 0, 10, 10]])
        assert len(matches) == 1
        assert fp == [] and fn == [1]

    def test_spurious_detection_is_a_false_positive(self):
        matches, fp, fn = match_frame([[0, 0, 10, 10]],
                                      [[0, 0, 10, 10], [50, 50, 60, 60]])
        assert len(matches) == 1
        assert fp == [1] and fn == []

    def test_duplicate_detections_cost_precision(self):
        """One ground-truth box can only absorb one detection."""
        gt = [[0, 0, 10, 10]]
        det = [[0, 0, 10, 10], [0, 0, 10, 10]]
        matches, fp, fn = match_frame(gt, det)
        assert len(matches) == 1
        assert len(fp) == 1 and fn == []

    def test_best_overlap_wins_the_pairing(self):
        gt = [[0, 0, 10, 10]]
        det = [[3, 0, 13, 10], [0, 0, 10, 10]]   # second is exact
        matches, fp, _ = match_frame(gt, det)
        assert matches == [(0, 1)]
        assert fp == [0]

    def test_overlap_below_threshold_is_not_a_match(self):
        # IoU here is 50/150 = 0.33, under the 0.5 default.
        matches, fp, fn = match_frame([[0, 0, 10, 10]], [[5, 0, 15, 10]])
        assert matches == []
        assert fp == [0] and fn == [0]

    def test_detection_inside_ignore_region_is_forgiven(self):
        """A vehicle straddling the frame edge must not be charged either way."""
        matches, fp, fn = match_frame(
            gt=[], det=[[0, 0, 10, 10]], ignore=[[0, 0, 20, 20]]
        )
        assert matches == [] and fn == []
        assert fp == [], "detection inside an ignore region should not count"

    def test_detection_outside_ignore_region_still_counts(self):
        matches, fp, fn = match_frame(
            gt=[], det=[[100, 100, 110, 110]], ignore=[[0, 0, 20, 20]]
        )
        assert fp == [0]


class TestDetectionScorer:
    def test_perfect_frame_scores_100(self):
        s = DetectionScorer()
        boxes = [[0, 0, 10, 10], [20, 20, 30, 30]]
        s.add_frame(boxes, boxes)
        d = s.summary()["detection"]
        assert d["precision"] == pytest.approx(1.0)
        assert d["recall"] == pytest.approx(1.0)
        assert d["f1"] == pytest.approx(1.0)

    def test_empty_frame_does_not_divide_by_zero(self):
        s = DetectionScorer()
        s.add_frame([], [])
        d = s.summary()["detection"]
        assert d["precision"] == 0.0 and d["recall"] == 0.0 and d["f1"] == 0.0

    def test_emergency_scored_only_over_located_vehicles(self):
        """A missed ambulance is a detection failure, not a classifier failure."""
        s = DetectionScorer()
        s.add_frame(
            gt_boxes=[[0, 0, 10, 10], [50, 50, 60, 60]],
            det_boxes=[[0, 0, 10, 10]],          # second vehicle missed entirely
            gt_emergency=[False, True],
            det_emergency=[False],
        )
        summary = s.summary()
        assert summary["detection"]["fn"] == 1
        # The missed ambulance must not also appear as a classifier miss.
        assert summary["emergency"]["fn"] == 0

    def test_emergency_false_positive_is_recorded(self):
        s = DetectionScorer()
        s.add_frame([[0, 0, 10, 10]], [[0, 0, 10, 10]],
                    gt_emergency=[False], det_emergency=[True])
        assert s.summary()["emergency"]["fp"] == 1

    def test_counting_mae_and_tolerance(self):
        s = DetectionScorer(count_tolerance=1)
        s.add_counts({"north": 5}, {"north": 5})   # exact
        s.add_counts({"north": 5}, {"north": 6})   # within tolerance
        s.add_counts({"north": 5}, {"north": 9})   # outside
        c = s.summary()["counting"]["north"]
        assert c["mae"] == pytest.approx((0 + 1 + 4) / 3)
        assert c["within_tolerance"] == pytest.approx(200 / 3)

    def test_counting_handles_approach_missing_from_one_side(self):
        s = DetectionScorer()
        s.add_counts({"north": 3}, {})            # detector found nothing
        assert s.summary()["counting"]["north"]["mae"] == pytest.approx(3.0)
