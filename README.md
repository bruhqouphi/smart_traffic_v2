# Smart Traffic — Adaptive Signal Control (v2)

An adaptive traffic-signal control system for a 4-way intersection. It uses
computer vision (YOLOv8) to count vehicles per approach, then benchmarks four
signal-timing controllers against each other in a software simulation to ask a
concrete question: **on a two-phase junction, what actually reduces average
wait — the order in which you pick phases, or how you allocate green time?**

On top of those controllers sits **emergency-vehicle preemption**: an ambulance
detected on any approach takes priority over whatever the controller was going
to do, and clears in ~5 s instead of the ~24–30 s an ordinary vehicle waits.
See [Emergency-vehicle priority](#emergency-vehicle-priority).

No hardware required — everything runs in simulation, including a synthetic
video generator so the full vision pipeline can be exercised without a camera
or real footage.

## The contribution: green-time allocation beats phase-selection

The headline finding (see [Findings](#findings)) is that on a two-phase
intersection, **how you size the green interval matters far more than which
phase you choose to serve next.** A saturation-flow green-allocation rule with
prompt alternation cuts average wait by up to 33% against a fixed-time baseline
and 22% against proportional control, while the "smart" phase-selection
heuristics (SJF vs max-pressure) turn out to make **no difference at all** once
fairness is enforced — a tight aging bound makes both collapse to prompt
alternation, producing bit-identical results.

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

## Emergency-vehicle priority

Ambulances, fire engines and police vehicles override all four controllers.
`EmergencyPreemptionController` is a **wrapper**, not a fifth algorithm — it
decorates any base controller and intercepts phase selection only while an
emergency vehicle (EV) is waiting. Every other decision passes straight through,
so all four controllers gain preemption without duplicating a line of logic, and
the with/without comparison is a like-for-like test of the same base strategy.

**The sequence.** Once an EV is detected on a phase:

1. That phase becomes the target. If it is already green, the green is *held*
   (up to `max_preempt_green`) so the interval cannot expire under the EV.
2. If the conflicting phase is green, its green is **truncated** — but not
   before `min_green_before_preempt` seconds have been served, because dropping
   a green instantly strands vehicles already entering the junction. Yellow and
   all-red then run **in full**: preemption skips the *wait*, never the
   clearance.
3. The target is held until the last EV departs, plus `clearance_extension`
   seconds, after which control returns to the base controller.

If both phases have an EV, the one already being served wins, so the controller
finishes clearing it rather than oscillating.

**In the queue model** an EV jumps to the head of its approach (ordinary traffic
pulls aside for a siren) and is exempt from `queue_capacity` — it is never
turned away as spillback. This is the priority-scheduling tier; the signal-level
preemption sits on top of it.

**Detection** is the honest weak point. COCO has no ambulance class, so
`EmergencyClassifier` identifies an EV by its light bar: saturated red and
saturated blue that are each a *small* share of the vehicle and present in
*comparable* amounts. The naive test — "does the box contain red and blue?" —
was tried first and flagged every blue car on the east approach, because blue
cars have red tail lights. Adjacency does not fix it either (the tail lights
touch the bodywork). Relative area does: a light bar is balanced, paintwork is
not. Measured on 11,473 vehicle detections of EV-free synthetic footage: **0
false positives**, while ambulances are flagged on all four approaches in both
flash states.

### Results

5 seeded trials × 600 s, `config/low_load_config.yaml`, pooled over all four
scenarios. EV response time against the wait an ordinary vehicle sees under the
same controller and demand:

| Algorithm             | EV wait | Ordinary wait | Reduction |
|-----------------------|:-------:|:-------------:|:---------:|
| `fixed`               | 4.3 s   | 30.0 s        | **−86%**  |
| `proportional`        | 5.3 s   | 27.4 s        | **−81%**  |
| `queue_clearing`      | 5.3 s   | 25.9 s        | **−80%**  |
| `longest_queue_first` | 5.2 s   | 23.9 s        | **−78%**  |

The reduction is largest under `fixed` precisely because `fixed` is the worst
baseline to be stuck behind — preemption is worth most where the underlying
controller is least responsive.

**What it costs everyone else.** Preemption is not free: every truncated green
throws away lost time (`yellow` + `all_red`) and serves a phase out of turn.
Average wait for ordinary traffic, EVP off vs on:

| Scenario     | fixed | proportional | queue_clearing | longest_queue_first |
|--------------|:-----:|:------------:|:--------------:|:-------------------:|
| balanced     | +0.6  | +1.8         | +1.9           | +0.9                |
| morning_rush | +3.0  | +4.6         | +6.4           | +3.4                |
| evening_rush | +2.6  | +3.9         | +3.4           | +3.1                |
| asymmetric   | +2.9  | +4.0         | +3.3           | −0.2                |

Seconds added to average wait, at an EV rate of 0.002/s per approach (~4 EVs per
600 s run). So roughly **1–6 s of extra delay for everyone buys a 78–86%
reduction in emergency response time** — the trade the proposal's
life-saving argument rests on, now measured rather than asserted.

Turn it all off with `--no-emergency` on any script, or by removing the
`emergency:` block from the config.

## Project structure

```
smart_traffic_v2/
├── config/
│   ├── default_config.yaml      # all parameters — no magic numbers in code
│   ├── low_load_config.yaml     # below-capacity demand + tuned aging bound (see Findings)
│   └── synthetic_roi.json        # ROI polygons for the synthetic video
├── src/
│   ├── detection/                # YOLOv8 + color detectors, video input, ROI counting,
│   │                             #   emergency_classifier.py (light-bar EV detection)
│   ├── signals/                  # timing_algorithms.py (the 4 controllers + the
│   │                             #   emergency preemption wrapper) + phase state machine
│   ├── simulation/               # Poisson arrivals, queue model, time-stepped engine
│   ├── metrics/                  # logging, summary stats, CSV export, statistical runner
│   └── visualization/            # Pygame real-time dashboard
├── scripts/                      # runnable entry points (see Usage)
├── tests/                        # pytest suite (97 tests)
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

# Demo footage with frequent ambulances. The config rate is realistic but rare
# (~1 EV per 8 min per approach), so raise it for a defence demo.
python scripts/generate_synthetic_video.py --scenario balanced --duration 120 --emergency-rate 0.01 --no-hud --output data/videos/synthetic_ev.mp4

# Any script can run the pre-emergency baseline with --no-emergency
python scripts/compare_algorithms.py --trials 5 --no-emergency --config config/low_load_config.yaml

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

`config/low_load_config.yaml` reuses the same four shapes at 30% of these rates
(peak 0.21 veh/s), which keeps every approach below capacity. That is the config
the headline results below come from; the rates above are deliberately
oversaturated. See [Findings](#findings).

### Dashboard controls

`SPACE` pause · `1`/`2`/`3`/`4` switch algorithm (fixed / proportional /
queue_clearing / longest_queue_first) · `Q` quit.

When an ambulance is detected the dashboard shows a flashing red alert band
across the top, draws that vehicle's bounding box in red labelled `EMERGENCY`,
and the signal panel's `EVP` line switches from `armed` to
`PREEMPTING <phase>` with a running count. Preemption needs an ROI file to know
*which* approach the EV is on — without one it stays off, and the existing
"NO ROI — counts ESTIMATED" warning applies.

## How the simulation works

- **Traffic generator** — Poisson arrivals per approach at the configured rates.
- **Queue model** — vehicles accumulate during red and depart at `saturation_flow`
  (default 1800 veh/h per approach) during green. The two approaches in a phase
  clear **simultaneously**, so clearance time uses `max(approach_a, approach_b)`,
  not the sum.
- **Amber discharge** — departures continue for the first `yellow_discharge_time`
  seconds of yellow (default 2.0 s of a 3 s interval), matching the real
  behaviour of vehicles already committed to the intersection. The remaining
  1 s is clearance lost time, within the usual 1–2 s range.
- **Turning movements** — each arrival is assigned a movement from the `turning:`
  split (default 70% through / 15% left / 15% right). A permitted left turn must
  yield to opposing through traffic, so it discharges at only 45% of saturation
  flow and therefore occupies `1 / 0.45` as much green; a right turn costs
  `1 / 0.85`. Because an approach is a single queue, a turning vehicle at the
  head **holds up everyone behind it** — the cost is head-of-line blocking, not
  just an averaged-down rate. Net effect at the default split: 1800 → 1611 veh/h.
- **Storage limit** — each approach holds at most `queue_capacity` vehicles
  (default 25, ≈ 175 m at ~7 m/vehicle). Arrivals that find it full are turned
  away and counted as `blocked` — the model's stand-in for spillback into the
  upstream link. This is what stops oversaturated runs from growing unbounded
  queues, and it makes **throughput**, not wait time, the thing to compare there.
- **Emergency vehicles** — arrive as a separate Poisson stream at
  `emergency.arrival_rate` per approach, on top of ordinary demand and drawn
  from their own RNG so enabling preemption cannot perturb the baseline arrival
  sequence. They jump to the head of their queue and ignore `queue_capacity`.
- **Engine** — a time-stepped loop (`dt = 0.1s`) drives the full
  `GREEN → YELLOW → ALL_RED → GREEN` state machine, feeds per-approach queue
  lengths to the active timing algorithm, and records metrics.
- **Metrics** — average/max wait time, average/max queue, throughput, cycle
  counts, blocked vehicles (count and % of demand), and emergency-vehicle
  response (count, average/max EV wait, preemptions triggered), exported to CSV.
  The statistical runner repeats N seeded trials and reports mean ± std.

## Findings

Each controller was run for 5 seeded trials × 600 s across all four scenarios
(`scripts/compare_algorithms.py --trials 5 --export`). Average wait time (s):

> **These tables are the `--no-emergency` baseline.** The green-allocation
> question is about ordinary traffic, so preemption is switched off here to keep
> it out of the comparison. Reproduce them with
> `--no-emergency`, or by removing the `emergency:` block from the config —
> both give these numbers exactly, and that is pinned by a test. With
> preemption on, every controller pays the 1–6 s shown in
> [Emergency-vehicle priority](#emergency-vehicle-priority), and the *ranking*
> below is unchanged.

### Below capacity — where green allocation is decided

`config/low_load_config.yaml`, tuned `max_wait_threshold: 20`. Every approach is
under capacity here: **0% of demand is blocked** in all sixteen runs, so nothing
in this table is an artifact of queues that had nowhere to go.

| Scenario     | fixed | proportional | queue_clearing | longest_queue_first |
|--------------|:-----:|:------------:|:--------------:|:-------------------:|
| balanced     | 20.1  | 17.2         | **13.5**       | **13.5**            |
| morning_rush | 30.8  | 25.8         | **23.8**       | **23.8**            |
| evening_rush | 29.0  | 25.3         | **22.9**       | **22.9**            |
| asymmetric   | 30.8  | **26.9**     | 28.3           | 28.3                |

Bold marks the lowest wait in each row. Four things stand out, and the project's
conclusions follow directly from them:

1. **Green allocation is the lever, not phase order.** The tuned adaptive
   controllers beat `fixed` on every scenario (−33% balanced, −23% morning,
   −21% evening, −8% asymmetric) and beat `proportional` on three of four
   (−22% / −8% / −10%), while running roughly twice the service cycles
   (29 vs 15). The gain comes from the saturation-flow green rule + prompt
   alternation, *not* from being clever about which phase to pick.

2. **SJF and max-pressure are indistinguishable under a tight aging bound.**
   `queue_clearing` and `longest_queue_first` produce *identical* results at
   `max_wait_threshold: 20`. A phase can only re-serve about every 15–20 s
   (`min_green` + `yellow` + `all_red`), so the aging rule fires on essentially
   every decision and overrides the selection heuristic — both collapse to
   prompt alternation. The phase-selection logic is effectively inert here.
   This is the central negative result: **on a two-phase junction there is no
   phase-order problem left to solve once aging is tight.**

3. **The aging bound dominates.** Sweeping it (`scripts/sweep_aging.py`) shows
   average wait falling monotonically as the bound tightens from 60 s → 20 s
   (balanced: 22.3 s → 13.5 s); the original 60 s default is what made the early
   adaptive results *lose* to the baselines. Below ~20 s the bound stops binding
   (the minimum cycle time takes over), which is why 10/15/20 give the same
   result.

4. **`proportional` wins on `asymmetric`, and that is expected.** With arrival
   rates of 0.21/0.03/0.12/0.06 the demand split is lopsided but *stable*, which
   is exactly the case a fixed demand-proportional split is built for. The
   adaptive controllers keep reacting to the three light approaches and pay the
   lost time (`yellow` + `all_red`) each time they switch. They still beat
   `fixed` here (28.3 vs 30.8) — the reactive machinery is not wasted, it is
   just out-earned by a static split when the split never needs to change.

### Above capacity — where wait time stops being the metric

`config/default_config.yaml`, 0.30 veh/s per approach on `balanced` against an
effective per-approach capacity of ~0.22 veh/s (1611 veh/h effective flow × a
green share of ~0.49): a volume-to-capacity ratio of about **1.4**. With
`queue_capacity: 25` the excess demand spills back instead of queueing forever.

| Scenario (balanced) | fixed | proportional | queue_clearing | longest_queue_first |
|---------------------|:-----:|:------------:|:--------------:|:-------------------:|
| avg wait (s)        | 92.4  | 92.2         | 84.0           | **82.1**            |
| throughput (veh)    | 434   | 437          | 444            | **449**             |
| blocked (% demand)  | 24.5  | 23.9         | 24.2           | **23.7**            |

Two conclusions, and they differ by scenario:

- On `balanced`, adaptive control still wins — but the honest headline is
  **throughput**, not wait: 449 vehicles served vs 434, and 0.8 pp less demand
  turned away. Wait time is a poor metric here because it is only measured over
  vehicles that *got through*.
- On the three rush scenarios everything converges (74.7–81.9 s wait,
  385–396 veh throughput, ~46% blocked, all within noise). When a single
  approach is far beyond capacity, no allocation of green helps — the binding
  constraint is the intersection's total capacity, not how it is divided.

Those runs are in `results/`; the below-capacity runs are in `results/low_load/`.

> **Note.** An earlier version of this model had no storage limit, and the
> oversaturated runs then showed *all* controllers converging on wait time. That
> convergence was partly an artifact of unbounded queues. With `queue_capacity`
> in place, the `balanced` case separates again on throughput; the rush cases
> genuinely do converge.

## Tests

```powershell
python -m pytest tests/ -q
```

Covers all four controllers (empty-queue, all-short, all-long, and aging edge
cases), the clearance-time formula and queue classification, and an end-to-end
simulation run. `longest_queue_first` has dedicated selection tests, including
one that pins its defining contrast with `queue_clearing` (serve the longest vs
the shortest queue on the same input). Also covers `saturation_flow` wiring,
amber discharge, queue capacity and spillback accounting, and turning movements
(share normalisation, config validation, the extra green a turn costs, and the
head-of-line blocking it causes) — including the fallbacks that keep configs
predating those keys reproducing the original numbers.

Emergency-vehicle priority adds tests for queue jumping and capacity exemption,
EV arrival generation, the preemption controller (target selection, overriding
even the aging rule, clearance-extension release, hook delegation), green
truncation and the guarantee that yellow and all-red still run in full, the
light-bar classifier — including regressions for the blue-car-with-red-tail-
lights false positive that the first version produced — and the end-to-end
guarantee that a config with no `emergency:` block reproduces the pre-emergency
results *bit-identically*. **166 tests, all passing.**

## Configuration

`config/default_config.yaml` holds all timing constraints, the Queue-Clearing
thresholds, scenario arrival rates, detection settings (vehicle classes,
confidence, model, frame skip), visualization colours, and metrics export
options. Edit it rather than touching the code.

These keys set the capacity of the model and are worth calling out. The three
`timing:` keys:

| Key | Default | Meaning |
|-----|:-------:|---------|
| `saturation_flow`      | 1800 veh/h | Discharge rate of one approach during green. Capacity per approach = `saturation_flow × (green ÷ cycle)`. |
| `yellow_discharge_time`| 2.0 s      | Seconds of the yellow interval still usable for discharge; clamped to `yellow_duration`. |
| `queue_capacity`       | 25 veh     | Storage limit per approach before arrivals are turned away as spillback. |

…and the `turning:` block, which sets the movement split and what each movement
costs. Shares are normalised, so writing them as percentages works too;
adjustments are HCM-style saturation-flow factors in (0, 1]:

| Key | Default | Meaning |
|-----|:-------:|---------|
| `through` / `left` / `right` | 0.70 / 0.15 / 0.15 | Share of arrivals making each movement. |
| `left_adjustment`  | 0.45 | A permitted left turn yields to opposing through traffic, so it discharges at 45% of saturation flow. |
| `right_adjustment` | 0.85 | A right turn is only mildly slowed. |

…and the `emergency:` block, which controls preemption:

| Key | Default | Meaning |
|-----|:-------:|---------|
| `enabled`                  | `true`  | Master switch. Absent block or `false` = no EVs generated, no controller wrapped. |
| `arrival_rate`             | 0.002 /s | EV arrivals per approach, on top of ordinary demand. ~1 per 8 min per approach. |
| `min_green_before_preempt` | 5.0 s   | Safety floor — an in-progress green must run this long before preemption truncates it. |
| `max_preempt_green`        | 45.0 s  | Hard cap on a preemption green, in case an EV never clears. |
| `clearance_extension`      | 3.0 s   | Hold after the last EV departs, so it is clear of the junction. |

Every one of these falls back to the model's historical behaviour when absent
from a config — `1800.0`, `0.0`, unlimited storage, all-through at full
saturation flow, and no emergency vehicles at all — so older config files still
reproduce the numbers they originally produced. That fallback is pinned by
tests, including one asserting that a run with `emergency:` removed is
*bit-identical* to one with `enabled: false`.

## Known limitations

Honest scope boundaries of the queue model, in the order they would most affect
the results:

1. **Turning is modelled as a service-time cost, not a spatial conflict.** A
   left-turner occupies more green and blocks the vehicles behind it, which
   captures the capacity and head-of-line effects. It does not model a turning
   vehicle *waiting in the intersection* for a gap, blocking the conflicting
   approach, or a dedicated turn lane letting through traffic past it.
2. **Spillback is counted, not propagated.** A full approach turns arrivals away
   and they are recorded as `blocked`, but there is no upstream link for them to
   back into and no feedback onto the adjacent intersection. This is the right
   abstraction for an isolated junction and the wrong one for a corridor.
3. **Two phases only.** No protected turn phases, so the phase-selection problem
   is binary — which is precisely why the aging bound dominates it (point 2 of
   [Findings](#findings)). A junction with protected turns would give the
   selection heuristics a real choice to make, and is the single most
   interesting extension of this work.
4. **`startup_lost_time` is used by the controller's green-time formula but not
   by the discharge process itself** — vehicles reach saturation flow instantly
   at the start of green rather than ramping up.
5. **Controllers see counts, not movements.** The timing algorithms are fed
   per-approach queue *lengths*, exactly as a real detector would report them,
   so they cannot know that a queue is full of left-turners and will take longer
   to clear than `headway × length` suggests. This mismatch between assumed and
   actual discharge is realistic, but it means none of the controllers here can
   exploit turn composition even in principle.
6. **Emergency-vehicle *detection* is a heuristic, not a trained classifier.**
   This is the weakest link in the whole pipeline and the one to be most careful
   about claiming. `EmergencyClassifier` looks for a balanced red-and-blue light
   bar; it therefore:
   - **misses a fire engine**, whose red bodywork swamps the balance test — the
     same rule that stops blue cars false-positiving causes this false negative;
   - misses any EV whose lights are off, or an unmarked police vehicle;
   - has been validated only on synthetic footage, where the light bar is drawn
     with known colours. The 0-false-positive figure quoted above is a property
     of that footage, **not** a claim about real CCTV.

   Everything downstream is indifferent to *how* the flag was set, so replacing
   this with a YOLO model fine-tuned on an emergency-vehicle dataset means
   rewriting one file and no others. That is the single highest-value next step
   for the vision half of the project.
7. **An EV jumps its queue instantly and is never blocked.** Real traffic takes
   time to pull aside, and a genuinely gridlocked approach may have nowhere to
   pull aside *to*. The model gives the EV a free path to the stop line, so the
   reported response times are a **lower bound** — the signal-side benefit of
   preemption, without the vehicle-side cost of getting through the queue.
8. **Preemption is measured on an isolated junction.** There is no upstream
   signal to hold traffic back and no green wave along the EV's route, which is
   where most of the real-world benefit of a corridor EVP system comes from.

## Stack

Python 3.10+ · ultralytics (YOLOv8) · opencv-python · pygame · numpy ·
matplotlib · pyyaml · pytest

## Author

Joshua Kissi — Final-Year Computer Science Project, KNUST, 2026.
