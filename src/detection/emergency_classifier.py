"""
Emergency-vehicle classification from a detected vehicle's pixels.

The COCO dataset that YOLOv8 ships with has no ambulance, police-car or
fire-truck class — it can tell you *that* something is a truck, never that the
truck is an ambulance. Rather than pretend otherwise, this module identifies an
emergency vehicle by the one feature that is visually unambiguous and does not
need a trained model: a **light bar showing saturated red and saturated blue
directly next to each other**.

Naively asking "does the box contain red AND blue?" does not work, and this
project measured that: a blue car has red tail lights, so every blue car on the
east approach was flagged. Neither does "are the red and blue adjacent?" — on a
blue car the red tail lights sit directly against blue bodywork.

What separates a light bar from paintwork is its *shape in colour-space*: the
two colours are each a small share of the vehicle, and they are present in
roughly equal amounts. Bodywork is the opposite — one colour dominates and the
other is a trim-sized speck. So a detection is flagged only when red and blue
are each

* above `min_lightbar_fraction`   — both genuinely present,
* below `max_lightbar_fraction`   — a fixture, not the paint job, and
* within `min_balance` of each other in area — a two-tone bar, not a body
  colour plus a tail light.

A fourth test is then applied to the two colours *together*: they must occupy
one compact region. A light bar is a single fixture, so the bounding box of all
its red and blue pixels covers a small part of the vehicle. This is what
separates a bar from a bus, whose blue-tinted side glazing runs the length of
the body while its red tail lights sit across the rear — individually balanced,
but spread over the whole vehicle. Balance alone flagged those buses.

This is a heuristic, not a learned classifier, and it is deliberately the
weakest link in the pipeline — see README > Known limitations. Everything
downstream (preemption, metrics, the dashboard alert) is indifferent to how the
flag was set, so swapping in a fine-tuned YOLO model later means replacing this
file and nothing else.
"""
from typing import Iterable, List

import cv2
import numpy as np

from src.detection.detector import Detection

# OpenCV hue is 0-179. Red wraps around the end of the range, so it needs two
# bands; blue is a single band around 110.
RED_BANDS = ((0, 10), (170, 179))
BLUE_BAND = (100, 130)


class EmergencyClassifier:
    """Flags detections whose pixels contain a red-and-blue light bar."""

    def __init__(
        self,
        min_lightbar_fraction: float = 0.015,
        min_saturation: int = 90,
        min_value: int = 90,
        band: float = 1.0,
        max_lightbar_fraction: float = 0.35,
        min_balance: float = 0.35,
        max_fixture_extent: float = 0.40,
    ):
        if not 0.0 < max_fixture_extent <= 1.0:
            raise ValueError("emergency_max_fixture_extent must be in (0, 1]")
        if not 0.0 < band <= 1.0:
            raise ValueError("emergency_lightbar_band must be in (0, 1]")
        if not 0.0 <= min_lightbar_fraction <= 1.0:
            raise ValueError("emergency_min_lightbar_fraction must be in [0, 1]")
        if not min_lightbar_fraction < max_lightbar_fraction <= 1.0:
            raise ValueError(
                "emergency_max_lightbar_fraction must be in "
                "(emergency_min_lightbar_fraction, 1]"
            )
        if not 0.0 < min_balance <= 1.0:
            raise ValueError("emergency_min_lightbar_balance must be in (0, 1]")
        self.min_lightbar_fraction = min_lightbar_fraction
        self.max_lightbar_fraction = max_lightbar_fraction
        self.min_balance = min_balance
        self.max_fixture_extent = max_fixture_extent
        self.min_saturation = min_saturation
        self.min_value = min_value
        self.band = band

    @classmethod
    def from_config(cls, config: dict) -> "EmergencyClassifier":
        d = config.get("detection", {})
        return cls(
            min_lightbar_fraction=d.get("emergency_min_lightbar_fraction", 0.015),
            max_lightbar_fraction=d.get("emergency_max_lightbar_fraction", 0.35),
            min_balance=d.get("emergency_min_lightbar_balance", 0.35),
            max_fixture_extent=d.get("emergency_max_fixture_extent", 0.40),
            min_saturation=d.get("emergency_min_saturation", 90),
            min_value=d.get("emergency_min_value", 90),
            band=d.get("emergency_lightbar_band", 1.0),
        )

    def _crop(self, frame: np.ndarray, det: Detection) -> np.ndarray:
        h, w = frame.shape[:2]
        x1 = max(0, int(det.x1))
        y1 = max(0, int(det.y1))
        x2 = min(w, int(det.x2))
        y2 = min(h, int(det.y2))
        if x2 <= x1 or y2 <= y1:
            return np.empty((0, 0, 3), dtype=frame.dtype)
        # Restrict to the top `band` of the box — the roof line, where a light
        # bar sits when the camera looks at the vehicle from the side.
        y2 = max(y1 + 1, y1 + int(round((y2 - y1) * self.band)))
        return frame[y1:y2, x1:x2]

    def is_emergency(self, frame: np.ndarray, det: Detection) -> bool:
        crop = self._crop(frame, det)
        if crop.size == 0:
            return False

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        hue, sat, val = cv2.split(hsv)
        bright = (sat >= self.min_saturation) & (val >= self.min_value)

        red = np.zeros(hue.shape, dtype=bool)
        for lo, hi in RED_BANDS:
            red |= (hue >= lo) & (hue <= hi)
        blue = (hue >= BLUE_BAND[0]) & (hue <= BLUE_BAND[1])

        total = float(hue.size)
        red_frac = float(np.count_nonzero(red & bright)) / total
        blue_frac = float(np.count_nonzero(blue & bright)) / total

        # Both present...
        if min(red_frac, blue_frac) < self.min_lightbar_fraction:
            return False
        # ...neither one is the bodywork...
        if max(red_frac, blue_frac) > self.max_lightbar_fraction:
            return False
        # ...they are comparable in area, as the two halves of a bar are...
        balance = min(red_frac, blue_frac) / max(red_frac, blue_frac)
        if balance < self.min_balance:
            return False

        # ...and together they form one compact fixture rather than being
        # scattered over the vehicle (bus glazing down the flanks, tail lights
        # across the rear).
        combined = (red | blue) & bright
        ys, xs = np.nonzero(combined)
        extent = ((ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)) / total
        # Cast explicitly: numpy's bool_ is not the `True` singleton, and
        # callers (and tests) treat this as a plain bool.
        return bool(extent <= self.max_fixture_extent)

    def classify(self, frame: np.ndarray, detections: Iterable[Detection]) -> List[Detection]:
        """Set `is_emergency` on each detection in place; returns the same list."""
        dets = list(detections)
        for det in dets:
            det.is_emergency = self.is_emergency(frame, det)
            if det.is_emergency:
                det.class_name = "emergency"
        return dets
