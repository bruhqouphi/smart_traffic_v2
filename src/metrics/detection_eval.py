"""
Scoring for the vision half of the system.

Two different questions are asked here, and keeping them apart matters:

1. *Detection* — did we find the vehicles, and nothing else? Standard
   precision / recall / F1 over boxes matched by IoU.
2. *Counting* — did each approach get the right number? This is the one the
   controller actually consumes: `timing_algorithms` never sees a bounding
   box, only `{approach: count}`. A detector can post mediocre IoU and still
   drive the signals perfectly, so counting accuracy is reported separately
   rather than inferred from box quality.

Emergency classification is scored only over *correctly located* vehicles, so
a missed ambulance is charged to detection rather than a second time to the
classifier.
"""
from typing import Dict, List, Sequence, Tuple

Box = Sequence[float]


def iou(a: Box, b: Box) -> float:
    """Intersection over union of two [x1, y1, x2, y2] boxes."""
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = ix2 - ix1, iy2 - iy1
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def ioa(box: Box, region: Box) -> float:
    """Share of `box` that falls inside `region` (intersection over box area)."""
    ix1, iy1 = max(box[0], region[0]), max(box[1], region[1])
    ix2, iy2 = min(box[2], region[2]), min(box[3], region[3])
    iw, ih = ix2 - ix1, iy2 - iy1
    if iw <= 0 or ih <= 0:
        return 0.0
    area = max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
    return (iw * ih) / area if area > 0 else 0.0


def match_frame(gt: Sequence[Box], det: Sequence[Box],
                ignore: Sequence[Box] = (), iou_threshold: float = 0.5,
                ignore_threshold: float = 0.5) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
    """
    Greedily pair ground-truth and detected boxes, best overlap first.

    Greedy-by-IoU is the standard assignment here: it is deterministic and
    cannot pair one ground-truth box with two detections, which is what makes
    duplicate detections count against precision the way they should.

    Detections left unmatched are forgiven if they mostly land inside an
    `ignore` region (a vehicle straddling the frame edge, which the generator
    declines to label either way).

    Returns (matches, false_positives, false_negatives) as index lists.
    """
    pairs = []
    for gi, g in enumerate(gt):
        for di, d in enumerate(det):
            score = iou(g, d)
            if score >= iou_threshold:
                pairs.append((score, gi, di))
    pairs.sort(key=lambda p: (-p[0], p[1], p[2]))

    matches: List[Tuple[int, int]] = []
    used_gt, used_det = set(), set()
    for _, gi, di in pairs:
        if gi in used_gt or di in used_det:
            continue
        used_gt.add(gi)
        used_det.add(di)
        matches.append((gi, di))

    false_pos = [
        di for di in range(len(det))
        if di not in used_det
        and not any(ioa(det[di], r) >= ignore_threshold for r in ignore)
    ]
    false_neg = [gi for gi in range(len(gt)) if gi not in used_gt]
    return matches, false_pos, false_neg


class DetectionScorer:
    """Accumulates per-frame results into overall detection/counting metrics."""

    def __init__(self, iou_threshold: float = 0.5, count_tolerance: int = 1):
        self.iou_threshold = iou_threshold
        # A queue count is "usable" if it is within this many vehicles of
        # truth. The timing rules key off queue *magnitude*, so being one car
        # out changes green time by well under a second.
        self.count_tolerance = count_tolerance

        self.tp = self.fp = self.fn = 0
        self.frames = 0
        # Emergency classification over correctly located vehicles.
        self.ev_tp = self.ev_fp = self.ev_fn = 0
        # Per-approach counting error.
        self._abs_err: Dict[str, List[int]] = {}
        self._within: Dict[str, List[bool]] = {}

    def add_frame(self, gt_boxes, det_boxes, ignore_boxes=(),
                  gt_emergency=None, det_emergency=None):
        self.frames += 1
        matches, fps, fns = match_frame(
            gt_boxes, det_boxes, ignore_boxes, self.iou_threshold
        )
        self.tp += len(matches)
        self.fp += len(fps)
        self.fn += len(fns)

        if gt_emergency is not None and det_emergency is not None:
            for gi, di in matches:
                g, d = bool(gt_emergency[gi]), bool(det_emergency[di])
                if g and d:
                    self.ev_tp += 1
                elif d and not g:
                    self.ev_fp += 1
                elif g and not d:
                    self.ev_fn += 1

    def add_counts(self, gt_counts: Dict[str, int], det_counts: Dict[str, int]):
        """Record per-approach queue counts for one frame."""
        for approach in set(gt_counts) | set(det_counts):
            err = abs(det_counts.get(approach, 0) - gt_counts.get(approach, 0))
            self._abs_err.setdefault(approach, []).append(err)
            self._within.setdefault(approach, []).append(err <= self.count_tolerance)

    @staticmethod
    def _prf(tp: int, fp: int, fn: int) -> Dict[str, float]:
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) else 0.0)
        return {"precision": precision, "recall": recall, "f1": f1,
                "tp": tp, "fp": fp, "fn": fn}

    def summary(self) -> dict:
        out = {
            "frames": self.frames,
            "detection": self._prf(self.tp, self.fp, self.fn),
            "emergency": self._prf(self.ev_tp, self.ev_fp, self.ev_fn),
            "counting": {},
        }
        all_err, all_within = [], []
        for approach in sorted(self._abs_err):
            errs = self._abs_err[approach]
            wins = self._within[approach]
            all_err.extend(errs)
            all_within.extend(wins)
            out["counting"][approach] = {
                "mae": sum(errs) / len(errs) if errs else 0.0,
                "within_tolerance": (100.0 * sum(wins) / len(wins)) if wins else 0.0,
            }
        out["counting"]["overall"] = {
            "mae": sum(all_err) / len(all_err) if all_err else 0.0,
            "within_tolerance": (100.0 * sum(all_within) / len(all_within))
                                if all_within else 0.0,
        }
        return out
