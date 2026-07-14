# Smart Traffic — Adaptive Signal Control (v2)

An adaptive traffic-signal control system for a 4-way intersection. It uses
computer vision (YOLOv8) to count vehicles per approach, then benchmarks four
signal-timing controllers against each other in a software simulation to ask a
concrete question: **on a two-phase junction, what actually reduces average
wait — the order in which you pick phases, or how you allocate green time?**

No hardware required — everything runs in simulation, including a synthetic
video generator so the full vision pipeline can be exercised without a camera
or real footage.

## The contribution: green-time allocation beats phase-selection

The headline finding (see [Findings](#findings)) is that on a two-phase
intersection, **how you size the green interval matters far more than which
phase you choose to serve next.** A saturation-flow green-allocation rule with
prompt alternation beats proportional control, while the "smart" phase-selection
heuristics (SJF vs max-pressure) turn out to make no difference once fairness is
enforced — because a tight aging bound makes both collapse to prompt alternation.

The four controllers:

| Algorithm             | Behaviour                                                                       |
|-----------------------|---------------------------------------------------------------------------------|
| `fixed`               | Fixed green time, strictly alternates NS ↔ EW (baseline).                       |
| `proportional`        | Alternates; green proportional to the served phase's *share* of the queue.      |
| `queue_clearing`      | SJF-inspired: serve the **shortest** queue first; queue-proportional green; age out starving approaches. |
| `longest_queue_first` | Max-pressure: serve the **largest** queue first; same green rule and aging as above. |

Shared green-duration rule (used by both adaptive controllers):
`green = startup_lost_time + queue × headway`, clamped to
`[long_queue_min_green, long_queue_max_green]` (short queues get a fixed
`short_queue_green` instead). This saturation-flow formula — not the phase-order
heuristic — is what drives the improvement over `proportional`.

**Aging:** if an approach hasn't been served in `max_wait_threshold` seconds,
it is promoted regardless of queue length to prevent starvation. This bound is
the single most important tuning parameter (see [Findings](#findings)).

All algorithms return phase IDs (`"NS"` / `"EW"`), enforced by an abstract base
class; `longest_queue_first` is implemented as a subclass of `queue_clearing`
that overrides only the phase-selection step.

## Project structure

```
smart_traffic_v2/
├── config/
│   ├── default_config.yaml      # all parameters — no magic numbers in code
│   ├── low_load_config.yaml     # unsaturated demand + tuned aging bound (see Findings)
│   └── synthetic_roi.json        # ROI polygons for the synthetic video
├── src/
│   ├── detection/                # YOLOv8 + color detectors, video input, ROI counting
│   ├── signals/                  # timing_algorithms.py (the 4 controllers) + phase state machine
│   ├── simulation/               # Poisson arrivals, queue model, time-stepped engine
│   ├── metrics/                  # logging, summary stats, CSV export, statistical runner
│   └── visualization/            # Pygame real-time dashboard
├── scripts/                      # runnable entry points (see Usage)
├── tests/                        # pytest suite (61 tests)
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
# Run a single simulation (algorithm ∈ fixed | proportional | queue_clearing | longest_queue_first)
python scripts/run_simulation.py --scenario balanced --algorithm longest_queue_first --duration 600 --seed 42

# Compare all 4 algorithms × all 4 scenarios over N trials, export CSVs
# (use the tuned low-load config for the unsaturated results in Findings)
python scripts/compare_algorithms.py --trials 5 --export --config config/low_load_config.yaml

# Sweep the aging bound (max_wait_threshold) for longest_queue_first
python scripts/sweep_aging.py --trials 5

# Generate comparison figures (bar / line / box plots) from the exported CSVs
python scripts/generate_plots.py --config config/low_load_config.yaml --output-dir results/low_load/plots

# Generate a synthetic traffic video (no camera needed)
python scripts/generate_synthetic_video.py --scenario morning_rush --duration 120 --output data/videos/synthetic.mp4

# Launch the live Pygame dashboard on a video. With --detector color the bundled
# synthetic ROI is loaded automatically so per-approach counts are real; pass
# --roi <file> to override. The dashboard uses config/low_load_config.yaml
# (tuned aging bound) by default.
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

`SPACE` pause · `1`/`2`/`3`/`4` switch algorithm (fixed / proportional /
queue_clearing / longest_queue_first) · `Q` quit.

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

## Findings

Each controller was run for 5 seeded trials × 600 s across all four scenarios
(`scripts/compare_algorithms.py --trials 5 --export`). Average wait time (s):

**Unsaturated demand** (`config/low_load_config.yaml`, tuned `max_wait_threshold: 20`):

| Scenario     | fixed | proportional | queue_clearing | longest_queue_first |
|--------------|:-----:|:------------:|:--------------:|:-------------------:|
| balanced     | 21.2  | 19.9         | **16.8**       | **16.8**            |
| morning_rush | 66.9  | **59.2**     | 61.6           | 61.6                |
| evening_rush | 69.1  | **59.4**     | 63.4           | 63.4                |
| asymmetric   | 52.7  | 66.4         | **61.6**       | **61.6**            |

Three things stand out, and the project's conclusions follow directly from them:

1. **Green allocation is the lever, not phase order.** The tuned adaptive
   controllers beat `proportional` on balanced (−16%) and asymmetric (−7%) and
   run more service cycles (28 vs 23). The gain comes from the saturation-flow
   green rule + prompt alternation, *not* from being clever about which phase to
   pick.

2. **SJF and max-pressure are indistinguishable under a tight aging bound.**
   `queue_clearing` and `longest_queue_first` produce *identical* results at
   `max_wait_threshold: 20`. A phase can only re-serve about every 15–20 s
   (`min_green` + `yellow` + `all_red`), so the aging rule fires on essentially
   every decision and overrides the selection heuristic — both collapse to
   prompt alternation. The phase-selection logic is effectively inert here.

3. **The aging bound dominates.** Sweeping it (`scripts/sweep_aging.py`) shows
   average wait falling monotonically as the bound tightens from 60 s → 20 s;
   the original 60 s default is what made the early adaptive results *lose* to
   the baselines. Below ~20 s the bound stops binding (the minimum cycle time
   takes over), which is why 10/15/20 give the same result.

Under near-saturated demand (`config/default_config.yaml`) all controllers
converge — when demand exceeds capacity, wait time is governed by arrival rate,
not signal logic, and no controller can help. Those runs are in `results/`; the
unsaturated runs above are in `results/low_load/`.

## Tests

```powershell
python -m pytest tests/ -q
```

Covers all four controllers (empty-queue, all-short, all-long, and aging edge
cases), the clearance-time formula and queue classification, and an end-to-end
simulation run. `longest_queue_first` has dedicated selection tests, including
one that pins its defining contrast with `queue_clearing` (serve the longest vs
the shortest queue on the same input). **61 tests, all passing.**

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
