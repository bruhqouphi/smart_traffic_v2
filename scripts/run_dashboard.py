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
    parser.add_argument("--config", default="config/default_config.yaml")
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"Error: video file not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    with open(args.config) as f:
        config = yaml.safe_load(f)

    if args.detector == "color":
        from src.detection.color_detector import ColorDetector
        detector = ColorDetector()
    else:
        from src.detection.detector import VehicleDetector
        detector = VehicleDetector(config["detection"])

    from src.visualization.dashboard import Dashboard
    dashboard = Dashboard(config, args.video, roi_path=args.roi, detector=detector)
    dashboard.run()


if __name__ == "__main__":
    main()
