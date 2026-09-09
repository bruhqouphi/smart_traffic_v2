#!/usr/bin/env python3
"""Sweep the aging (max_wait_threshold) parameter for both adaptive controllers.

Runs `queue_clearing` (SJF) and `longest_queue_first` (max-pressure) side by
side at several aging thresholds, with `proportional` (the strongest baseline)
as a fixed reference line.

Running BOTH controllers is the point. The headline result is that they produce
identical output under a tight bound, and identical numbers look like a bug
until you can show the same two controllers diverging when the bound is
loosened. This sweep is that evidence: it locates the threshold at which the
phase-selection rule stops being unreachable.
"""
import argparse
import copy
import csv
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.metrics.collector import run_statistical_trials

SCENARIOS = ["balanced", "morning_rush", "evening_rush", "asymmetric"]
THRESHOLDS = [10, 15, 20, 25, 30, 45, 60, 90]
PAIR = ["queue_clearing", "longest_queue_first"]

# Two runs count as identical when their mean and spread agree to this
# tolerance. Exact float equality is the real claim, so the tolerance only
# exists to absorb formatting noise, not genuine differences.
EPS = 1e-9


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=600.0)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--config", default="config/low_load_config.yaml")
    parser.add_argument("--no-emergency", action="store_true",
                        help="Disable emergency vehicles and preemption, "
                             "whatever the config says. The README's aging "
                             "figures are this baseline — without it the "
                             "1-6s preemption cost is folded into every cell.")
    parser.add_argument("--export", default=None, metavar="PATH",
                        help="Write the sweep to CSV for the report.")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        base_config = yaml.safe_load(f)

    if args.no_emergency:
        base_config.setdefault("emergency", {})["enabled"] = False

    from src.signals.timing_algorithms import emergency_enabled
    ev_note = "emergency ON" if emergency_enabled(base_config) else "emergency OFF"

    # Reference baseline: proportional avg wait per scenario.
    ref = {}
    for s in SCENARIOS:
        r = run_statistical_trials(base_config, "proportional", s,
                                   args.duration, args.trials)
        ref[s] = r["avg_wait"]["mean"]

    print(f"\nAvg wait (s) -- queue_clearing (SJF) / longest_queue_first (max-pressure)")
    print(f"vs aging threshold ({args.trials} trials, {args.config}, {ev_note})")

    col = "{:>10} " + " ".join(["{:>17}"] * len(SCENARIOS)) + " {:>11}"
    width = 11 + 18 * len(SCENARIOS) + 12
    print()
    print(col.format("threshold", *SCENARIOS, "identical?"))
    print("-" * width)
    print(col.format("proportional",
                     *[f"{ref[s]:.1f}" for s in SCENARIOS], ""))
    print("-" * width)

    rows = []
    for thr in THRESHOLDS:
        cfg = copy.deepcopy(base_config)
        cfg["timing"]["max_wait_threshold"] = thr
        cells, all_same = [], True
        for s in SCENARIOS:
            res = {}
            for algo in PAIR:
                r = run_statistical_trials(cfg, algo, s, args.duration, args.trials)
                res[algo] = (r["avg_wait"]["mean"], r["avg_wait"]["std"])
            (m_qc, s_qc), (m_lq, s_lq) = res[PAIR[0]], res[PAIR[1]]
            same = abs(m_qc - m_lq) < EPS and abs(s_qc - s_lq) < EPS
            all_same &= same
            cells.append(f"{m_qc:.1f} / {m_lq:.1f}{'' if same else ' *'}")
            rows.append({"threshold": thr, "scenario": s,
                         "queue_clearing": round(m_qc, 4),
                         "longest_queue_first": round(m_lq, 4),
                         "identical": same})
        print(col.format(str(thr), *cells, "YES" if all_same else "no"))

    print("\n* = the two controllers differ on that scenario")
    print("A row marked YES means the aging bound fired on every decision, so the")
    print("phase-selection rule was never reached and both controllers collapsed")
    print("to prompt alternation.")

    if args.export:
        os.makedirs(os.path.dirname(os.path.abspath(args.export)), exist_ok=True)
        with open(args.export, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"\nWrote {args.export}")


if __name__ == "__main__":
    main()
