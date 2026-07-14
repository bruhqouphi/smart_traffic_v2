"""
Color-based vehicle detector for the synthetic traffic video.
Finds brightly-coloured vehicle blobs via HSV saturation thresholding
and contour detection — no YOLO required.
"""
from typing import List

import cv2
import numpy as np

from src.detection.detector import Detection


class ColorDetector:
    """
    Detects the coloured vehicle rectangles in the synthetic video.
    Works by finding high-saturation blobs (vehicles) against the
    low-saturation grey road background.
    """

    def __init__(self, min_area: int = 400, min_saturation: int = 50,
                 min_value: int = 55):
        self.min_area = min_area
        self.min_saturation = min_saturation
        self.min_value = min_value
        kernel_size = 3
        self._kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (kernel_size, kernel_size)
        )

    @classmethod
    def from_config(cls, config: dict) -> "ColorDetector":
        """Build from the `detection` block, falling back to defaults."""
        d = config.get("detection", {})
        return cls(
            min_area=d.get("color_min_area", 400),
            min_saturation=d.get("color_min_saturation", 50),
            min_value=d.get("color_min_value", 55),
        )

    def detect(self, frame: np.ndarray) -> List[Detection]:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        _, sat, val = cv2.split(hsv)

        # Vehicles are colourful (high sat) and not black
        sat_mask = cv2.threshold(sat, self.min_saturation, 255, cv2.THRESH_BINARY)[1]
        val_mask = cv2.threshold(val, self.min_value, 255, cv2.THRESH_BINARY)[1]
        mask = cv2.bitwise_and(sat_mask, val_mask)

        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  self._kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel)

        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        detections: List[Detection] = []
        for cnt in contours:
            if cv2.contourArea(cnt) < self.min_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            detections.append(Detection(
                x1=float(x),     y1=float(y),
                x2=float(x + w), y2=float(y + h),
                confidence=1.0,
                class_id=2,
                class_name="car",
            ))
        return detections
