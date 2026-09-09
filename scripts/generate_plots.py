#!/usr/bin/env python3
import argparse
import csv
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ALGORITHMS = ["fixed", "proportional", "queue_clearing", "longest_queue_first"]
SCENARIOS = ["balanced", "morning_rush", "evening_rush", "asymmetric"]


def main():
    parser = argparse.ArgumentParser(
        description="Generate comparison plots from exported CSVs."
    )
    parser.add_argument("--export-dir", default=None)
    parser.add_argument("--output-dir", default="results/plots")
    parser.add_argument("--config", default="config/default_config.yaml")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    export_dir = args.export_dir or config["metrics"]["export_dir"]

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    os.makedirs(args.output_dir, exist_ok=True)

    comparison_path = os.path.join(export_dir, "comparison.csv")
    if not os.path.exists(comparison_path):
        print(f"comparison.csv not found at {comparison_path}")
        print("Run first:  python scripts/compare_algorithms.py --export")
        sys.exit(1)

    with open(comparison_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    def row_val(algo, scenario, key):
        r = next(r for r in rows if r["algorithm"] == algo and r["scenario"] == scenario)
        return float(r[key])

    # 1. Grouped bar chart: avg wait time
    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(SCENARIOS))
    w = 0.8 / len(ALGORITHMS)
    for i, algo in enumerate(ALGORITHMS):
        vals = [row_val(algo, s, "avg_wait_mean") for s in SCENARIOS]
        errs = [row_val(algo, s, "avg_wait_std") for s in SCENARIOS]
        ax.bar(x + i * w, vals, w, label=algo, yerr=errs, capsize=4)
    ax.set_xticks(x + w * (len(ALGORITHMS) - 1) / 2)
    ax.set_xticklabels(SCENARIOS, rotation=12)
    ax.set_ylabel("Average Wait Time (s)")
    ax.set_title("Average Wait Time by Algorithm and Scenario")
    ax.legend()
    plt.tight_layout()
    out1 = os.path.join(args.output_dir, "avg_wait_bar.png")
    plt.savefig(out1, dpi=150)
    plt.close()
    print(f"Saved {out1}")

    # 2. Box plots: wait distribution per algorithm
    fig, axes = plt.subplots(1, len(ALGORITHMS), figsize=(14, 5), sharey=True)
    for ax, algo in zip(axes, ALGORITHMS):
        data = []
        for scenario in SCENARIOS:
            wpath = os.path.join(export_dir, f"{algo}_{scenario}_waits.csv")
            if os.path.exists(wpath):
                with open(wpath, encoding="utf-8") as f:
                    waits = [float(r["wait_time"]) for r in csv.DictReader(f)]
                data.append(waits if waits else [0.0])
            else:
                data.append([0.0])
        ax.boxplot(data, tick_labels=SCENARIOS, patch_artist=True)
        ax.set_title(algo)
        ax.tick_params(axis="x", rotation=15)
    axes[0].set_ylabel("Wait Time (s)")
    plt.suptitle("Wait Time Distribution by Algorithm")
    plt.tight_layout()
    out2 = os.path.join(args.output_dir, "wait_boxplot.png")
    plt.savefig(out2, dpi=150)
    plt.close()
    print(f"Saved {out2}")

    # 3. Queue history line chart (balanced scenario)
    fig, ax = plt.subplots(figsize=(12, 5))
    for algo in ALGORITHMS:
        qpath = os.path.join(export_dir, f"{algo}_balanced_queues.csv")
        if not os.path.exists(qpath):
            continue
        times, totals = [], []
        with open(qpath, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                times.append(float(r["time"]))
                totals.append(sum(float(v) for k, v in r.items() if k != "time"))
        step = max(len(times) // 300, 1)
        ax.plot(times[::step], totals[::step], label=algo, alpha=0.85)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Total Queue Length (vehicles)")
    ax.set_title("Queue History - balanced scenario")
    ax.legend()
    plt.tight_layout()
    out3 = os.path.join(args.output_dir, "queue_history.png")
    plt.savefig(out3, dpi=150)
    plt.close()
    print(f"Saved {out3}")

    print(f"\nAll plots saved to {args.output_dir}/")


if __name__ == "__main__":
    main()
