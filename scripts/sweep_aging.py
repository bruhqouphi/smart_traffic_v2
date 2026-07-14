#!/usr/bin/env python3
"""Sweep the aging (max_wait_threshold) parameter for longest_queue_first.

Runs LQF at several aging thresholds across all scenarios and prints avg wait,
with `proportional` (the strongest baseline) as a fixed reference line.
"""
import argparse
import copy
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.metrics.collector import run_statistical_trials

SCENARIOS = ["balanced", "morning_rush", "evening_rush", "asymmetric"]
THRESHOLDS = [10, 15, 20, 25, 30, 45, 60]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=600.0)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--config", default="config/low_load_config.yaml")
    args = parser.parse_args()

    with open(args.config) as f:
        base_config = yaml.safe_load(f)

    # Reference baseline: proportional avg wait per scenario.
    ref = {}
    for s in SCENARIOS:
        r = run_statistical_trials(base_config, "proportional", s, args.duration, args.trials)
        ref[s] = r["avg_wait"]["mean"]

    print(f"\nAvg wait (s) -- longest_queue_first vs aging threshold "
          f"({args.trials} trials, {args.config})")
    fmt = "{:>12} " + " ".join(["{:>14}"] * len(SCENARIOS))
    print(fmt.format("threshold", *SCENARIOS))
    print("-" * (13 + 15 * len(SCENARIOS)))
    print(fmt.format("proportional", *[f"{ref[s]:.1f}" for s in SCENARIOS]))
    print("-" * (13 + 15 * len(SCENARIOS)))

    for thr in THRESHOLDS:
        cfg = copy.deepcopy(base_config)
        cfg["timing"]["max_wait_threshold"] = thr
        cells = []
        for s in SCENARIOS:
            r = run_statistical_trials(cfg, "longest_queue_first", s, args.duration, args.trials)
            avg = r["avg_wait"]["mean"]
            mark = "*" if avg < ref[s] else " "
            cells.append(f"{avg:.1f}{mark}")
        print(fmt.format(str(thr), *cells))

    print("\n* = beats proportional for that scenario")


if __name__ == "__main__":
    main()
