from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np


VEHICLE_CLASSES = {1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


@dataclass
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int
    class_name: str
    # Optional tracking metadata. `counted` is None in the legacy mode where the
    # detector behaves exactly as before; when `counting_line_y` is configured it
    # becomes True/False to indicate whether the tracked vehicle has already
    # crossed the counting line.
    track_id: Optional[int] = None
    counted: Optional[bool] = None
    bottom_y: Optional[float] = None
    # Set by EmergencyClassifier, not by the detector itself — COCO has no
    # emergency-vehicle class. Defaults False so a detector that never runs the
    # classifier behaves exactly as before.
    is_emergency: bool = False

    @property
    def center(self):
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def bbox(self):
        return (self.x1, self.y1, self.x2, self.y2)


class VehicleDetector:
    def __init__(self, config: dict, emergency_classifier=None):
        self.confidence_threshold = config.get("confidence_threshold", 0.4)
        self.counting_line_y = config.get("counting_line_y")
        # Optional: flags detected vehicles as emergency vehicles by their light
        # bar. Without one, `Detection.is_emergency` stays False everywhere.
        self.emergency_classifier = emergency_classifier
        self.model = None
        self._counted_ids: set[int] = set()
        self._prev_bottom_by_track: Dict[int, float] = {}
        self._load_model(config.get("model", "yolov8n.pt"))

    def _load_model(self, model_path: str):
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
        except ImportError:
            raise RuntimeError("ultralytics not installed. Run: pip install ultralytics")

    def detect(self, frame: np.ndarray) -> List[Detection]:
        if self.model is None:
            return []
        results = self.model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False,
        )[0]

        detections: List[Detection] = []
        for box in results.boxes:
            class_id = int(box.cls[0])
            if class_id not in VEHICLE_CLASSES:
                continue
            conf = float(box.conf[0])
            if conf < self.confidence_threshold:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            track_id = None
            if box.id is not None:
                track_id = int(box.id[0])

            counted = None
            if self.counting_line_y is not None and track_id is not None:
                prev_bottom_y = self._prev_bottom_by_track.get(track_id)
                if prev_bottom_y is None:
                    counted = False
                else:
                    counted = prev_bottom_y < self.counting_line_y <= y2
                    if counted:
                        self._counted_ids.add(track_id)
                if track_id in self._counted_ids:
                    counted = True

            detections.append(Detection(
                x1=x1, y1=y1, x2=x2, y2=y2,
                confidence=conf,
                class_id=class_id,
                class_name=VEHICLE_CLASSES[class_id],
                track_id=track_id,
                counted=counted,
                bottom_y=y2,
            ))

            if track_id is not None:
                self._prev_bottom_by_track[track_id] = float(y2)

        if self.emergency_classifier is not None:
            self.emergency_classifier.classify(frame, detections)
        return detections
