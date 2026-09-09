#!/usr/bin/env python3
import argparse
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="Launch Pygame traffic dashboard.")
    parser.add_argument("video", help="Path to traffic video file")
    parser.add_argument("--roi", default=None, help="Path to ROI config JSON")
    parser.add_argument("--detector", choices=["yolo", "color"], default="yolo",
                        help="yolo=YOLOv8 (real video), color=contour detection (synthetic video)")
    # low_load_config carries the tuned aging bound (max_wait_threshold=20); the
    # scenario arrival rates in it are unused here since queues come from video.
    parser.add_argument("--config", default="config/low_load_config.yaml")
    parser.add_argument("--no-emergency", action="store_true",
                        help="Disable emergency-vehicle detection and signal "
                             "preemption for this run, whatever the config says.")
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"Error: video file not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    with open(args.config, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # For the synthetic (color) demo, default to the bundled ROI so per-approach
    # counts are real rather than an even split of the total.
    roi_path = args.roi
    if roi_path is None and args.detector == "color":
        default_roi = "config/synthetic_roi.json"
        if os.path.exists(default_roi):
            roi_path = default_roi
            print(f"Using default ROI: {default_roi}")

    if args.no_emergency:
        config.setdefault("emergency", {})["enabled"] = False

    # The classifier is what turns a detected vehicle into a *emergency* vehicle
    # — without it nothing is ever flagged and preemption can never fire.
    from src.signals.timing_algorithms import emergency_enabled
    classifier = None
    if emergency_enabled(config):
        from src.detection.emergency_classifier import EmergencyClassifier
        classifier = EmergencyClassifier.from_config(config)

    if args.detector == "color":
        from src.detection.color_detector import ColorDetector
        detector = ColorDetector.from_config(config, emergency_classifier=classifier)
    else:
        from src.detection.detector import VehicleDetector
        detector = VehicleDetector(config["detection"], emergency_classifier=classifier)

    from src.visualization.dashboard import Dashboard
    dashboard = Dashboard(config, args.video, roi_path=roi_path, detector=detector)
    dashboard.run()


if __name__ == "__main__":
    main()
