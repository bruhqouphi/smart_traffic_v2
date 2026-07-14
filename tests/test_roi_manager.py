"""Tests for ROIManager per-approach counting, incl. the overlap de-dup fix."""
from src.detection.detector import Detection
from src.detection.roi_manager import ROIManager


def _det_at(cx, cy):
    """A 2x2 detection centred on (cx, cy)."""
    return Detection(
        x1=cx - 1, y1=cy - 1, x2=cx + 1, y2=cy + 1,
        confidence=1.0, class_id=2, class_name="car",
    )


def _square(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


class TestCountPerApproach:
    def test_counts_vehicle_in_its_approach(self):
        mgr = ROIManager()
        mgr.add_roi("lane_n", "north", _square(0, 0, 100, 100))
        counts = mgr.count_vehicles_per_approach([_det_at(50, 50)])
        assert counts.get("north", 0) == 1

    def test_vehicle_outside_all_rois_not_counted(self):
        mgr = ROIManager()
        mgr.add_roi("lane_n", "north", _square(0, 0, 100, 100))
        counts = mgr.count_vehicles_per_approach([_det_at(500, 500)])
        assert sum(counts.values()) == 0

    def test_overlapping_rois_count_vehicle_once(self):
        # Two ROIs (different approaches) overlap over the region containing the
        # vehicle. It must be counted once total, not once per ROI.
        mgr = ROIManager()
        mgr.add_roi("lane_n", "north", _square(0, 0, 100, 100))
        mgr.add_roi("lane_e", "east", _square(50, 50, 150, 150))
        counts = mgr.count_vehicles_per_approach([_det_at(75, 75)])
        assert sum(counts.values()) == 1

    def test_multiple_vehicles_across_approaches(self):
        mgr = ROIManager()
        mgr.add_roi("lane_n", "north", _square(0, 0, 100, 100))
        mgr.add_roi("lane_s", "south", _square(0, 200, 100, 300))
        counts = mgr.count_vehicles_per_approach(
            [_det_at(50, 50), _det_at(60, 60), _det_at(50, 250)]
        )
        assert counts["north"] == 2
        assert counts["south"] == 1
