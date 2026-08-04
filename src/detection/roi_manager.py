import json
from typing import Dict, List, Set, Tuple


class ROIManager:
    """Polygon-based ROI manager; counts vehicles per lane / approach."""

    def __init__(self):
        # {lane_name: {"approach": str, "polygon": List[Tuple[int,int]]}}
        self.rois: Dict[str, dict] = {}

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
        for det in detections:
            for roi in self.rois.values():
                if self._pip(*det.center, roi["polygon"]):
                    approach = roi["approach"]
                    counts[approach] = counts.get(approach, 0) + 1
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
        with open(path, "w") as f:
            json.dump(self.rois, f, indent=2)

    def load(self, path: str):
        with open(path, "r") as f:
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
