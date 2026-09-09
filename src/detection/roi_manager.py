import json
from typing import Dict, List, Set, Tuple


class ROIManager:
    """Polygon-based ROI manager; counts vehicles per lane / approach."""

    def __init__(self):
        # {lane_name: {"approach": str, "polygon": List[Tuple[int,int]]}}
        self.rois: Dict[str, dict] = {}
        self._counted_track_ids: Set[int] = set()

    def add_roi(self, lane_name: str, approach: str, polygon: List[Tuple[int, int]]):
        self.rois[lane_name] = {"approach": approach, "polygon": list(polygon)}

    def _pip(self, px: float, py: float, polygon: List[Tuple[int, int]]) -> bool:
        """Ray-casting point-in-polygon test."""
        n = len(polygon)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            if ((yi > py) != (yj > py)) and (
                px < (xj - xi) * (py - yi) / ((yj - yi) or 1e-10) + xi
            ):
                inside = not inside
            j = i
        return inside

    def count_vehicles_per_approach(self, detections) -> Dict[str, int]:
        # Each vehicle is counted at most once: the first ROI whose polygon
        # contains its centre wins. This prevents a vehicle in overlapping ROIs
        # from being counted for two approaches.
        counts: Dict[str, int] = {}
        class_counts = self.count_vehicles_by_class_per_approach(detections)
        for approach, by_class in class_counts.items():
            counts[approach] = sum(by_class.values())
        return counts

    def count_vehicles_by_class_per_approach(self, detections) -> Dict[str, Dict[str, int]]:
        """Return per-approach counts organised by vehicle class.

        In the legacy/no-line mode, every detection is counted exactly as before.
        In line-tracking mode, vehicles are counted once when they cross the
        configured counting line, using the tracked `counted` flag and `track_id`
        to prevent recounting on later frames.
        """
        counts: Dict[str, Dict[str, int]] = {}

        for det in detections:
            track_id = getattr(det, "track_id", None)
            counted = getattr(det, "counted", None)

            # Legacy mode: no line-based counting configured, so preserve the
            # original behaviour and count every detection in every frame.
            if counted is None:
                pass
            else:
                if not counted:
                    continue
                if track_id is not None and track_id in self._counted_track_ids:
                    continue
                if track_id is not None:
                    self._counted_track_ids.add(track_id)

            for roi in self.rois.values():
                if self._pip(*det.center, roi["polygon"]):
                    approach = roi["approach"]
                    counts.setdefault(approach, {})
                    counts[approach][det.class_name] = (
                        counts[approach].get(det.class_name, 0) + 1
                    )
                    break

        return counts

    def emergency_approaches(self, detections) -> Set[str]:
        """
        Approaches whose ROI contains a detection flagged as an emergency
        vehicle. Empty unless a classifier has set `is_emergency`.
        """
        found: Set[str] = set()
        for det in detections:
            if not getattr(det, "is_emergency", False):
                continue
            for roi in self.rois.values():
                if self._pip(*det.center, roi["polygon"]):
                    found.add(roi["approach"])
                    break
        return found

    def count_vehicles_per_lane(self, detections) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for lane_name, roi in self.rois.items():
            counts[lane_name] = sum(
                1 for det in detections if self._pip(*det.center, roi["polygon"])
            )
        return counts

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.rois, f, indent=2)

    def load(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.rois = {
            k: {"approach": v["approach"], "polygon": [tuple(p) for p in v["polygon"]]}
            for k, v in data.items()
        }

    @classmethod
    def from_file(cls, path: str) -> "ROIManager":
        mgr = cls()
        mgr.load(path)
        return mgr

    def get_polygons_for_display(self) -> Dict[str, List[Tuple[int, int]]]:
        return {name: roi["polygon"] for name, roi in self.rois.items()}
