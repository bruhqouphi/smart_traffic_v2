#!/usr/bin/env python3
"""Measure detection accuracy against generated ground truth.

Answers the "how accurate is the vision half?" question with a number instead
of an assertion. Pair it with footage made by:

  python scripts/generate_synthetic_video.py --no-hud \
      --output data/videos/eval.mp4 --ground-truth data/videos/eval_truth.json

then:

  python scripts/evaluate_detection.py --video data/videos/eval.mp4 \
      --ground-truth data/videos/eval_truth.json --detector color
"""
import argparse
import json
import os
import sys

import cv2
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.detection.roi_manager import ROIManager
from src.metrics.detection_eval import DetectionScorer


class _Point:
    """Minimal stand-in so ground-truth boxes can reuse ROIManager."""

    def __init__(self, bbox, is_emergency=False):
        self.bbox_ = bbox
        self.is_emergency = is_emergency

    @property
    def center(self):
        x1, y1, x2, y2 = self.bbox_
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def build_detector(name: str, config: dict):
    from src.detection.emergency_classifier import EmergencyClassifier
    classifier = EmergencyClassifier.from_config(config)
    if name == "color":
        from src.detection.color_detector import ColorDetector
        return ColorDetector.from_config(config, emergency_classifier=classifier)
    from src.detection.detector import VehicleDetector
    # VehicleDetector takes the `detection` block directly, unlike
    # ColorDetector.from_config which takes the whole config.
    return VehicleDetector(config["detection"], emergency_classifier=classifier)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--ground-truth", required=True)
    p.add_argument("--config", default="config/low_load_config.yaml")
    p.add_argument("--detector", default="color", choices=["color", "yolo"])
    p.add_argument("--roi", default="config/synthetic_roi.json")
    p.add_argument("--iou", type=float, default=0.5)
    p.add_argument("--frame-step", type=int, default=1,
                   help="Score every Nth frame. Consecutive frames are highly "
                        "correlated, so stepping trades a little precision for "
                        "a lot of runtime on the YOLO path.")
    p.add_argument("--count-tolerance", type=int, default=1)
    p.add_argument("--export", default=None, metavar="PATH",
                   help="Write the summary as JSON.")
    args = p.parse_args()

    with open(args.config, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    with open(args.ground_truth, encoding="utf-8") as f:
        truth = json.load(f)

    if truth.get("meta", {}).get("hud"):
        print("WARNING: ground truth was generated with the HUD on. The "
              "overlay is unlabelled saturated colour and will be scored as "
              "false positives. Regenerate with --no-hud.\n")

    detector = build_detector(args.detector, config)
    rois = ROIManager.from_file(args.roi) if os.path.exists(args.roi) else None
    scorer = DetectionScorer(iou_threshold=args.iou,
                             count_tolerance=args.count_tolerance)

    by_index = {f["frame"]: f for f in truth["frames"]}
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"cannot open {args.video}")

    fi = scored = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        gt = by_index.get(fi)
        fi_now, fi = fi, fi + 1
        if gt is None or fi_now % args.frame_step:
            continue

        detections = detector.detect(frame)
        det_boxes = [list(d.bbox) for d in detections]
        det_ev = [bool(getattr(d, "is_emergency", False)) for d in detections]
        gt_boxes = [v["bbox"] for v in gt["vehicles"]]
        gt_ev = [v["is_emergency"] for v in gt["vehicles"]]

        scorer.add_frame(gt_boxes, det_boxes, gt.get("ignore", ()),
                         gt_emergency=gt_ev, det_emergency=det_ev)

        if rois is not None:
            gt_pts = [_Point(v["bbox"], v["is_emergency"]) for v in gt["vehicles"]]
            scorer.add_counts(rois.count_vehicles_per_approach(gt_pts),
                              rois.count_vehicles_per_approach(detections))
        scored += 1
        if scored % 250 == 0:
            print(f"  scored {scored} frames...")
    cap.release()

    s = scorer.summary()
    d, e = s["detection"], s["emergency"]
    print(f"\nDetection accuracy -- {args.detector} detector, "
          f"IoU>={args.iou}, {s['frames']} frames scored")
    print("-" * 62)
    print(f"  precision      {d['precision']*100:6.2f}%   "
          f"(TP {d['tp']}, FP {d['fp']})")
    print(f"  recall         {d['recall']*100:6.2f}%   "
          f"(TP {d['tp']}, FN {d['fn']})")
    print(f"  F1             {d['f1']*100:6.2f}%")

    print(f"\nEmergency classification (over correctly located vehicles)")
    print("-" * 62)
    print(f"  precision      {e['precision']*100:6.2f}%   "
          f"(TP {e['tp']}, FP {e['fp']})")
    print(f"  recall         {e['recall']*100:6.2f}%   "
          f"(TP {e['tp']}, FN {e['fn']})")

    print(f"\nPer-approach queue count (what the controller consumes)")
    print("-" * 62)
    print(f"  {'approach':<12} {'MAE (veh)':>10} {'within +/-' + str(args.count_tolerance):>14}")
    for approach, c in s["counting"].items():
        label = approach if approach != "overall" else "OVERALL"
        print(f"  {label:<12} {c['mae']:>10.2f} {c['within_tolerance']:>13.1f}%")

    if args.export:
        os.makedirs(os.path.dirname(os.path.abspath(args.export)), exist_ok=True)
        with open(args.export, "w", encoding="utf-8") as f:
            json.dump({"config": vars(args), "summary": s}, f, indent=2)
        print(f"\nWrote {args.export}")


if __name__ == "__main__":
    main()
