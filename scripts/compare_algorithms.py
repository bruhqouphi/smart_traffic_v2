#!/usr/bin/env python3
import argparse
import csv
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.metrics.collector import run_statistical_trials

ALGORITHMS = ["fixed", "proportional", "queue_clearing", "longest_queue_first"]
SCENARIOS = ["balanced", "morning_rush", "evening_rush", "asymmetric"]


def main():
    parser = argparse.ArgumentParser(
        description="Compare all algorithms across all scenarios."
    )
    parser.add_argument("--duration", type=float, default=600.0)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--export", action="store_true",
                        help="Export comparison CSV and per-run CSVs")
    parser.add_argument("--config", default="config/default_config.yaml")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    all_results = {}
    for algo in ALGORITHMS:
        for scenario in SCENARIOS:
            key = f"{algo}/{scenario}"
            print(f"Running {key} ({args.trials} trials)...", end=" ", flush=True)
            result = run_statistical_trials(
                config, algo, scenario, args.duration, args.trials
            )
            all_results[key] = result
            print(f"avg_wait={result['avg_wait']['mean']:.1f}s")

    # Comparison table
    col = "{:<20} {:<16} {:>12} {:>12} {:>12} {:>8}"
    print(f"\n{col.format('Algorithm', 'Scenario', 'AvgWait+/-std', 'MaxWait+/-std', 'Throughput', 'Cycles')}")
    print("-" * 86)
    for algo in ALGORITHMS:
        for scenario in SCENARIOS:
            r = all_results[f"{algo}/{scenario}"]
            print(col.format(
                algo, scenario,
                f"{r['avg_wait']['mean']:.1f}+/-{r['avg_wait']['std']:.1f}",
                f"{r['max_wait']['mean']:.1f}+/-{r['max_wait']['std']:.1f}",
                f"{r['throughput']['mean']:.0f}",
                f"{r['num_cycles']['mean']:.0f}",
            ))

    if args.export:
        export_dir = config["metrics"]["export_dir"]
        os.makedirs(export_dir, exist_ok=True)

        # Summary CSV
        cpath = os.path.join(export_dir, "comparison.csv")
        fields = ["algorithm", "scenario",
                  "avg_wait_mean", "avg_wait_std",
                  "max_wait_mean", "max_wait_std",
                  "throughput_mean", "num_cycles_mean"]
        with open(cpath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for algo in ALGORITHMS:
                for scenario in SCENARIOS:
                    r = all_results[f"{algo}/{scenario}"]
                    writer.writerow({
                        "algorithm": algo, "scenario": scenario,
                        "avg_wait_mean": r["avg_wait"]["mean"],
                        "avg_wait_std": r["avg_wait"]["std"],
                        "max_wait_mean": r["max_wait"]["mean"],
                        "max_wait_std": r["max_wait"]["std"],
                        "throughput_mean": r["throughput"]["mean"],
                        "num_cycles_mean": r["num_cycles"]["mean"],
                    })
        print(f"\nSummary CSV: {cpath}")

        # Detailed per-algo/scenario CSVs (single deterministic run each)
        from src.signals.timing_algorithms import get_algorithm
        from src.simulation.sim_engine import SimEngine

        for algo in ALGORITHMS:
            for scenario in SCENARIOS:
                a = get_algorithm(algo, config)
                engine = SimEngine(config, a, scenario=scenario, seed=0)
                m = engine.run(args.duration)
                m.export_csv(export_dir, f"{algo}_{scenario}")
        print(f"Detailed CSVs: {export_dir}/")


if __name__ == "__main__":
    main()
