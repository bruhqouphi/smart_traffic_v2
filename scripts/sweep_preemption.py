#!/usr/bin/env python3
"""Sweep the preemptive-scheduling knobs and compare against non-preemptive.

Answers the question the `preemptive:` config block exists for: does making a
controller preemptive (SRTF-style, re-deciding mid-green) help ordinary traffic
the way emergency preemption helps ambulances?

Three views:
  --mode compare  every controller, preemptive vs not
  --mode floor    sweep min_service_before_preempt (the quantum's floor)
  --mode margin   sweep margin_vehicles (hysteresis)

Emergency preemption is switched off throughout so the scheduling question is
measured on its own.
"""
import argparse
import copy
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.metrics.collector import run_statistical_trials

ALGORITHMS = ["fixed", "proportional", "queue_clearing", "longest_queue_first"]
SCENARIOS = ["balanced", "morning_rush", "evening_rush", "asymmetric"]
FLOORS = [2.0, 5.0, 8.0, 10.0, 15.0, 25.0]
MARGINS = [0, 1, 2, 3, 5]


def base_configs(path: str):
    """(non-preemptive, preemptive) pair, both with emergency disabled."""
    with open(path) as f:
        cfg = yaml.safe_load(f)
    cfg.setdefault("emergency", {})["enabled"] = False
    cfg.setdefault("preemptive", {})
    off = copy.deepcopy(cfg)
    off["preemptive"]["enabled"] = False
    on = copy.deepcopy(cfg)
    on["preemptive"]["enabled"] = True
    return off, on


def wait(cfg, algo, scenario, args) -> dict:
    return run_statistical_trials(cfg, algo, scenario, args.duration, args.trials)


def mode_compare(off, on, args):
    print(f"\nAvg wait (s): preemptive vs non-preemptive "
          f"({args.trials} trials, {args.config})")
    fmt = "{:<21} {:<14} {:>12} {:>12} {:>8} {:>10} {:>8}"
    print(fmt.format("algorithm", "scenario", "non-preempt", "preemptive",
                     "delta", "switches", "cycles"))
    print("-" * 92)
    for algo in ALGORITHMS:
        for s in SCENARIOS:
            a = wait(off, algo, s, args)
            b = wait(on, algo, s, args)
            wa, wb = a["avg_wait"]["mean"], b["avg_wait"]["mean"]
            print(fmt.format(
                algo, s, f"{wa:.1f}", f"{wb:.1f}", f"{wb - wa:+.1f}",
                f"{b['sched_preemptions']['mean']:.0f}",
                f"{b['num_cycles']['mean']:.0f}",
            ))


def mode_sweep(off, on, args, key, values, label):
    ref = wait(off, args.algorithm, args.scenario, args)["avg_wait"]["mean"]
    print(f"\n{args.algorithm} / {args.scenario} — {label} sweep "
          f"({args.trials} trials, {args.config})")
    print(f"non-preemptive reference: {ref:.1f}s\n")
    fmt = "{:>10} {:>8} {:>10} {:>8}"
    print(fmt.format(label, "wait", "switches", "cycles"))
    print("-" * 40)
    for v in values:
        cfg = copy.deepcopy(on)
        cfg["preemptive"][key] = v
        r = wait(cfg, args.algorithm, args.scenario, args)
        avg = r["avg_wait"]["mean"]
        mark = "*" if avg < ref else " "
        print(fmt.format(
            str(v), f"{avg:.1f}{mark}",
            f"{r['sched_preemptions']['mean']:.0f}",
            f"{r['num_cycles']['mean']:.0f}",
        ))
    print("\n* = beats the non-preemptive controller")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["compare", "floor", "margin"],
                        default="compare")
    parser.add_argument("--algorithm", default="longest_queue_first",
                        choices=ALGORITHMS, help="used by floor/margin modes")
    parser.add_argument("--scenario", default="balanced", choices=SCENARIOS,
                        help="used by floor/margin modes")
    parser.add_argument("--duration", type=float, default=600.0)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--config", default="config/low_load_config.yaml")
    args = parser.parse_args()

    off, on = base_configs(args.config)
    if args.mode == "compare":
        mode_compare(off, on, args)
    elif args.mode == "floor":
        mode_sweep(off, on, args, "min_service_before_preempt", FLOORS,
                   "min_service")
    else:
        mode_sweep(off, on, args, "margin_vehicles", MARGINS, "margin")


if __name__ == "__main__":
    main()
