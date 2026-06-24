#!/usr/bin/env python3
import argparse
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.signals.timing_algorithms import get_algorithm
from src.simulation.sim_engine import SimEngine


def main():
    parser = argparse.ArgumentParser(description="Run a single traffic simulation.")
    parser.add_argument("--scenario", default="balanced",
                        choices=["balanced", "morning_rush", "evening_rush", "asymmetric"])
    parser.add_argument("--algorithm", default="queue_clearing",
                        choices=["fixed", "proportional", "queue_clearing"])
    parser.add_argument("--duration", type=float, default=600.0,
                        help="Simulation duration in seconds")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--export", action="store_true",
                        help="Export metrics to CSV files")
    parser.add_argument("--config", default="config/default_config.yaml")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    algo = get_algorithm(args.algorithm, config)
    engine = SimEngine(config, algo, scenario=args.scenario, seed=args.seed)
    metrics = engine.run(args.duration)
    summary = metrics.summary()

    print(f"\n{'='*52}")
    print(f"  Algorithm : {args.algorithm}")
    print(f"  Scenario  : {args.scenario}")
    print(f"  Duration  : {args.duration:.0f}s  |  seed={args.seed}")
    print(f"{'='*52}")
    for k, v in summary.items():
        print(f"  {k:<20} {v:>10.2f}")

    if args.export:
        export_dir = config["metrics"]["export_dir"]
        prefix = f"{args.algorithm}_{args.scenario}"
        paths = metrics.export_csv(export_dir, prefix)
        print(f"\nCSVs exported:")
        for label, path in paths.items():
            print(f"  {label}: {path}")


if __name__ == "__main__":
    main()
