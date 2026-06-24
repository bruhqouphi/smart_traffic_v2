# Smart Traffic — Adaptive Signal Control (v2)

An adaptive traffic-signal control system for a 4-way intersection. It uses
computer vision (YOLOv8) to count vehicles per approach and an **SJF-inspired
Queue-Clearing algorithm** to decide signal timing, then benchmarks that
algorithm against Fixed and Proportional baselines in a software simulation.

No hardware required — everything runs in simulation, including a synthetic
video generator so the full vision pipeline can be exercised without a camera
or real footage.

## The academic contribution: Queue-Clearing

A Shortest-Job-First-inspired controller with an aging mechanism:

| Algorithm        | Behaviour                                                          |
|------------------|-------------------------------------------------------------------|
| `fixed`          | Fixed green time, strictly alternates NS ↔ EW (baseline).         |
| `proportional`   | Green time proportional to the served phase's share of the queue. |
| `queue_clearing` | Serve short queues first; extend green for long queues; **age out** starving approaches. |

Queue-Clearing logic:
- Classify each approach's queue as **short** (≤ `short_queue_threshold`, default 5) or **long**.
- When short and long queues coexist, **serve the shortest first** (SJF).
- When only long queues exist, give green time proportional to queue length:
  `green = startup_lost_time + queue × headway`, clamped to `[long_queue_min_green, long_queue_max_green]`.
- **Aging:** if an approach hasn't been served in `max_wait_threshold` seconds
  (default 60), promote it regardless of queue length to prevent starvation.

All algorithms return phase IDs (`"NS"` / `"EW"`), enforced by an abstract base class.

## Project structure

```
smart_traffic_v2/
├── config/
│   ├── default_config.yaml      # all parameters — no magic numbers in code
│   └── synthetic_roi.json        # ROI polygons for the synthetic video
├── src/
│   ├── detection/                # YOLOv8 + color detectors, video input, ROI counting
│   ├── signals/                  # timing_algorithms.py (the 3 algos) + phase state machine
│   ├── simulation/               # Poisson arrivals, queue model, time-stepped engine
│   ├── metrics/                  # logging, summary stats, CSV export, statistical runner
│   └── visualization/            # Pygame real-time dashboard
├── scripts/                      # runnable entry points (see Usage)
├── tests/                        # pytest suite (52 tests)
├── data/videos/                  # input/synthetic videos (gitignored)
├── results/                      # exported CSVs and plots (gitignored)
└── requirements.txt
```

## Setup

```powershell
# from the smart_traffic_v2 folder
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate         # macOS / Linux

pip install -r requirements.txt
```

The YOLOv8 weights (`yolov8n.pt`) download automatically on first detection run.

## Usage

All scripts read every parameter from `config/default_config.yaml`.

```powershell
# Run a single simulation
python scripts/run_simulation.py --scenario balanced --algorithm queue_clearing --duration 600 --seed 42

# Compare all 3 algorithms × all 4 scenarios over N trials, export CSVs
python scripts/compare_algorithms.py --trials 5 --export

# Generate comparison figures (bar / line / box plots) from the exported CSVs
python scripts/generate_plots.py --output-dir results/plots

# Generate a synthetic traffic video (no camera needed)
python scripts/generate_synthetic_video.py --scenario morning_rush --duration 120 --output data/videos/synthetic.mp4

# Launch the live Pygame dashboard on a video
python scripts/run_dashboard.py data/videos/synthetic.mp4 --detector color

# Interactively define lane ROI polygons on a video
python scripts/calibrate_roi.py data/videos/synthetic.mp4 --output config/roi_config.json
```

### Scenarios

Defined in `config/default_config.yaml` as per-approach arrival rates (vehicles/second):

| Scenario       | north | south | east | west |
|----------------|:-----:|:-----:|:----:|:----:|
| `balanced`     | 0.3   | 0.3   | 0.3  | 0.3  |
| `morning_rush` | 0.5   | 0.2   | 0.6  | 0.1  |
| `evening_rush` | 0.2   | 0.5   | 0.1  | 0.6  |
| `asymmetric`   | 0.7   | 0.1   | 0.4  | 0.2  |

### Dashboard controls

`SPACE` pause · `1`/`2`/`3` switch algorithm · `Q` quit.

## How the simulation works

- **Traffic generator** — Poisson arrivals per approach at the configured rates.
- **Queue model** — vehicles accumulate during red and depart at saturation flow
  during green. The two approaches in a phase clear **simultaneously**, so
  clearance time uses `max(approach_a, approach_b)`, not the sum.
- **Engine** — a time-stepped loop (`dt = 0.1s`) drives the full
  `GREEN → YELLOW → ALL_RED → GREEN` state machine, feeds per-approach queue
  lengths to the active timing algorithm, and records metrics.
- **Metrics** — average/max wait time, average/max queue, throughput, and cycle
  counts, exported to CSV. The statistical runner repeats N seeded trials and
  reports mean ± std.

## Tests

```powershell
python -m pytest tests/ -q
```

Covers all three timing algorithms (including empty-queue, all-short, all-long,
and aging edge cases), the clearance-time formula and queue classification, and
an end-to-end simulation run. **52 tests, all passing.**

## Configuration

`config/default_config.yaml` holds all timing constraints, the Queue-Clearing
thresholds, scenario arrival rates, detection settings (vehicle classes,
confidence, model, frame skip), visualization colours, and metrics export
options. Edit it rather than touching the code.

## Stack

Python 3.10+ · ultralytics (YOLOv8) · opencv-python · pygame · numpy ·
matplotlib · pyyaml · pytest

## Author

Joshua Kissi — Final-Year Computer Science Project, KNUST, 2026.
