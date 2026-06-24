#!/usr/bin/env python3
"""
ROI calibration tool.
Opens the first frame of a video; user clicks polygon vertices per lane.
Enter = confirm lane, N = skip lane, S = save & exit, Q = quit without saving.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

APPROACHES = ["north", "south", "east", "west"]


class ROICalibrator:
    def __init__(self, video_path: str, output_path: str):
        self.video_path = video_path
        self.output_path = output_path
        self.rois: dict = {}
        self.current_points = []
        self.frame: np.ndarray = None
        self.display: np.ndarray = None
        self.lane_name = ""
        self.approach = ""

    def _get_first_frame(self):
        cap = cv2.VideoCapture(self.video_path)
        ret, frame = cap.read()
        cap.release()
        return frame if ret else None

    def _redraw(self):
        self.display = self.frame.copy()
        # Committed ROIs
        for name, roi in self.rois.items():
            pts = np.array(roi["polygon"], np.int32)
            cv2.polylines(self.display, [pts], True, (0, 255, 0), 2)
            cx = int(np.mean([p[0] for p in roi["polygon"]]))
            cy = int(np.mean([p[1] for p in roi["polygon"]]))
            cv2.putText(self.display, name, (cx - 20, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        # In-progress polygon
        if self.current_points:
            pts = np.array(self.current_points, np.int32)
            cv2.polylines(self.display, [pts], False, (0, 180, 255), 2)
            for p in self.current_points:
                cv2.circle(self.display, p, 5, (255, 80, 0), -1)
        lines = [
            f"Lane: {self.lane_name}  (approach={self.approach})",
            "Click to add vertices",
            "Enter=confirm  N=skip  S=save  Q=quit",
        ]
        for i, txt in enumerate(lines):
            cv2.putText(self.display, txt, (10, 26 + i * 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.imshow("ROI Calibration", self.display)

    def _mouse_cb(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.current_points.append((x, y))
            self._redraw()

    def run(self):
        self.frame = self._get_first_frame()
        if self.frame is None:
            print("Could not read a frame from the video.")
            return

        cv2.namedWindow("ROI Calibration", cv2.WINDOW_NORMAL)
        cv2.setMouseCallback("ROI Calibration", self._mouse_cb)

        lanes = [(f"lane_{a}", a) for a in APPROACHES]
        idx = 0

        while idx < len(lanes):
            self.lane_name, self.approach = lanes[idx]
            self.current_points = []
            self._redraw()

            while True:
                key = cv2.waitKey(0) & 0xFF
                if key == 13:  # Enter - confirm
                    if len(self.current_points) >= 3:
                        self.rois[self.lane_name] = {
                            "approach": self.approach,
                            "polygon": list(self.current_points),
                        }
                        print(f"ROI saved: {self.lane_name}")
                        self.current_points = []
                        self._redraw()
                        break
                    print("Need at least 3 vertices. Keep clicking.")
                elif key in (ord("n"), ord("N")):
                    print(f"Skipped {self.lane_name}")
                    break
                elif key in (ord("s"), ord("S")):
                    self._save()
                    cv2.destroyAllWindows()
                    return
                elif key in (ord("q"), ord("Q")):
                    print("Quit without saving.")
                    cv2.destroyAllWindows()
                    return
            idx += 1

        self._save()
        cv2.destroyAllWindows()

    def _save(self):
        if not self.rois:
            print("No ROIs defined - nothing saved.")
            return
        os.makedirs(os.path.dirname(os.path.abspath(self.output_path)), exist_ok=True)
        with open(self.output_path, "w") as f:
            json.dump(self.rois, f, indent=2)
        print(f"ROI config saved: {self.output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Interactively define ROI polygons per lane."
    )
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--output", default="config/roi_config.json",
                        help="Output JSON path (default: config/roi_config.json)")
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"Error: video not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    ROICalibrator(args.video, args.output).run()


if __name__ == "__main__":
    main()
