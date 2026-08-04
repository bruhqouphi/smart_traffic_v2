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
    parser.add_argument("--no-emergency", action="store_true",
                        help="Disable emergency vehicles and preemption, "
                             "whatever the config says.")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    if args.no_emergency:
        config.setdefault("emergency", {})["enabled"] = False

    from src.signals.timing_algorithms import emergency_enabled
    show_ev = emergency_enabled(config)

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
    col = "{:<20} {:<16} {:>12} {:>12} {:>12} {:>8} {:>9}"
    header = col.format('Algorithm', 'Scenario', 'AvgWait+/-std', 'MaxWait+/-std',
                        'Throughput', 'Cycles', 'Blocked%')
    ev_col = "  {:>7} {:>10} {:>10}"
    if show_ev:
        header += ev_col.format('EVs', 'EVWait', 'Preempts')
    print(f"\n{header}")
    print("-" * len(header))
    for algo in ALGORITHMS:
        for scenario in SCENARIOS:
            r = all_results[f"{algo}/{scenario}"]
            row = col.format(
                algo, scenario,
                f"{r['avg_wait']['mean']:.1f}+/-{r['avg_wait']['std']:.1f}",
                f"{r['max_wait']['mean']:.1f}+/-{r['max_wait']['std']:.1f}",
                f"{r['throughput']['mean']:.0f}",
                f"{r['num_cycles']['mean']:.0f}",
                f"{r['blocked_pct']['mean']:.1f}",
            )
            if show_ev:
                row += ev_col.format(
                    f"{r['ev_served']['mean']:.1f}",
                    f"{r['avg_ev_wait']['mean']:.1f}",
                    f"{r['preemptions']['mean']:.1f}",
                )
            print(row)

    if show_ev:
        # The headline EVP number: how much shorter an emergency vehicle's wait
        # is than an ordinary vehicle's, under the same controller and demand.
        print("\nEmergency-vehicle response (all scenarios pooled):")
        for algo in ALGORITHMS:
            ev = [all_results[f"{algo}/{s}"]["avg_ev_wait"]["mean"] for s in SCENARIOS]
            ordinary = [all_results[f"{algo}/{s}"]["avg_wait"]["mean"] for s in SCENARIOS]
            ev_mean = sum(ev) / len(ev)
            ord_mean = sum(ordinary) / len(ordinary)
            saved = (100.0 * (ord_mean - ev_mean) / ord_mean) if ord_mean else 0.0
            print(f"  {algo:<22} EV {ev_mean:5.1f}s vs ordinary {ord_mean:5.1f}s "
                  f"({saved:+.0f}%)")

    if args.export:
        export_dir = config["metrics"]["export_dir"]
        os.makedirs(export_dir, exist_ok=True)

        # Summary CSV
        cpath = os.path.join(export_dir, "comparison.csv")
        fields = ["algorithm", "scenario",
                  "avg_wait_mean", "avg_wait_std",
                  "max_wait_mean", "max_wait_std",
                  "throughput_mean", "num_cycles_mean",
                  "blocked_mean", "blocked_pct_mean",
                  "ev_served_mean", "avg_ev_wait_mean", "max_ev_wait_mean",
                  "preemptions_mean"]
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
                        "blocked_mean": r["blocked"]["mean"],
                        "blocked_pct_mean": r["blocked_pct"]["mean"],
                        "ev_served_mean": r["ev_served"]["mean"],
                        "avg_ev_wait_mean": r["avg_ev_wait"]["mean"],
                        "max_ev_wait_mean": r["max_ev_wait"]["mean"],
                        "preemptions_mean": r["preemptions"]["mean"],
                    })
        print(f"\nSummary CSV: {cpath}")

        # Detailed per-algo/scenario CSVs (single deterministic run each)
        from src.signals.timing_algorithms import build_controller
        from src.simulation.sim_engine import SimEngine

        for algo in ALGORITHMS:
            for scenario in SCENARIOS:
                a = build_controller(algo, config)
                engine = SimEngine(config, a, scenario=scenario, seed=0)
                m = engine.run(args.duration)
                m.export_csv(export_dir, f"{algo}_{scenario}")
        print(f"Detailed CSVs: {export_dir}/")


if __name__ == "__main__":
    main()
