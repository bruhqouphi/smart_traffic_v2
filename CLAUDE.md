# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

Adaptive traffic-signal control for a 4-way intersection (Final-Year CS Project,
KNUST, 2026). Research question: **on a two-phase junction, what reduces average
wait — the order in which you pick phases, or how you allocate green time?**
Headline finding: green-time allocation is the lever; phase-selection heuristics
collapse to prompt alternation under a tight aging bound. See `README.md` for the
full findings table.

Emergency-vehicle preemption sits on top of all four controllers and delivers a
78–86% cut in EV response time for 1–6 s of extra delay to everyone else. It is
a *wrapper* (`EmergencyPreemptionController`), not a fifth algorithm — see
`README.md` → Emergency-vehicle priority.

Everything runs in simulation. No hardware required.

## Commands

```powershell
.\.venv\Scripts\Activate.ps1

python -m pytest tests/ -q                 # 166 tests
python scripts/run_simulation.py --scenario balanced --algorithm longest_queue_first --duration 600 --seed 42
python scripts/compare_algorithms.py --trials 5 --export --config config/low_load_config.yaml
python scripts/sweep_aging.py --trials 5
python scripts/run_dashboard.py data/videos/synthetic.mp4 --detector color

# Emergency-vehicle demo footage (config rate is realistic but rare)
python scripts/generate_synthetic_video.py --scenario balanced --duration 120 --emergency-rate 0.01 --no-hud --output data/videos/synthetic_ev.mp4

# The pre-emergency baseline — every script takes --no-emergency
python scripts/compare_algorithms.py --trials 5 --no-emergency --config config/low_load_config.yaml
```

Build controllers with `build_controller(name, config)`, **not**
`get_algorithm`. The former applies the emergency wrapper when the config
enables it; the latter deliberately returns the bare controller and is for tests
and internal use.

All parameters live in `config/*.yaml`. Edit config, not code — there should be no
magic numbers in source.

---

# Simulation Strategy (decided — do not revisit without explicit request)

## Primary simulator stays custom

`src/simulation/` (point-queue / Poisson model) is the basis for **all thesis
results**. Reasons:

- Isolates the green-time-allocation research question cleanly
- Fast and deterministic, so parameter sweeps are cheap
- Already validated by 97 existing tests

**Do not propose rewriting this in SUMO or SimPy.**

## SUMO is optional, secondary, validation-only

Add only if time permits (~1–2 weeks). Not required for the thesis.

- **Scope:** single 4-way node, two phases, no turning movements initially
- **Implementation:** TraCI control loop calling `traci.trafficlight.setPhase()`
- **Reuse the existing controller classes** from `src/signals/timing_algorithms.py`
  directly — do not duplicate logic, only build the I/O adapter
- **Queue lengths:** from `traci.lanearea` (E2) detectors
- **Goal:** validate that the *ranking* of algorithms holds (e.g. `queue_clearing`
  beats `proportional` on balanced/asymmetric scenarios) — **not** to match
  absolute wait times, which are expected to differ from the custom sim
- **Output:** `sumo-gui` screenshots + one ranking-comparison chart
  (custom sim vs SUMO), used as a validation slide, not a live demo

## Pygame dashboard is the live defence demo — keep as-is

`src/visualization/dashboard.py` runs a **completely separate pipeline** from the
custom sim: real video → YOLO detection → ROI vehicle counts → the same controller
classes from `timing_algorithms.py`.

- Do **not** merge this with `SimEngine`
- Do **not** try to render SUMO state through Pygame
- Preserve and polish:
  - live YOLO bounding boxes
  - ROI polygon overlays
  - live per-approach vehicle counts
  - keys `1`–`4` for hot-swapping algorithms mid-demo
  - on-screen readout of current phase / green time remaining / active algorithm
  - the flashing emergency alert band, red `EMERGENCY` bounding boxes, and the
    `EVP: armed | PREEMPTING <phase>` status line

## matplotlib is for thesis numbers only

`compare_algorithms.py`, `sweep_aging.py` → CSV → charts. Not part of any live demo.

---

# Priority gaps in the custom sim — all three closed

1. ~~No turning movements~~ — **done.** `turning:` config block; each arrival is
   assigned through/left/right, and a turn costs `1/adjustment` as much green.
   Because an approach is a single queue this also produces head-of-line
   blocking. See `TurningMix` in `src/simulation/intersection.py`.
2. ~~No spillback / queue capacity limit~~ — **done.** `timing.queue_capacity`
   caps each approach; refused arrivals are counted as `blocked` and surfaced in
   `MetricsCollector.summary()` and `comparison.csv`. This resolved the
   "all controllers converge" artifact: under oversaturation the `balanced`
   scenario now separates on *throughput* rather than wait time.
3. ~~Departures ignore the yellow phase~~ — **done.** `timing.yellow_discharge_time`
   (`SimEngine._is_discharging`).

Every one of these keys falls back to the model's pre-existing behaviour when
absent from a config, and that fallback is pinned by tests — so old configs
still reproduce the numbers they originally produced. Preserve this property.
**The `emergency:` block follows the same rule**: removing it (or setting
`enabled: false`) must reproduce the pre-preemption results bit-identically, and
`TestBackwardCompatibility` in `tests/test_emergency.py` asserts exactly that.
EVs are drawn from a separate RNG stream for the same reason — enabling
preemption must never perturb the ordinary Poisson arrival sequence.

Note that the Findings tables in `README.md` are the `--no-emergency` baseline.
If you re-measure them, pass that flag or the numbers will not match.

Note: `config/low_load_config.yaml` rates were retuned to 30% of
`default_config.yaml` when turning movements cut effective flow to 1611 veh/h.
The invariant that matters is **0% blocked on all four scenarios** — that is
what makes it the below-capacity regime. Check `blocked_pct` before changing
those rates.

Remaining known limitations are documented in `README.md` → Known limitations.
The most interesting extension is protected turn phases (>2 phases), which would
give the phase-selection heuristics a real choice to make.

## Emergency-vehicle detection — be honest about this one

`src/detection/emergency_classifier.py` is a **light-bar heuristic, not a
trained classifier**, because COCO has no ambulance class. It looks for
saturated red and blue that are each a small share of the vehicle and balanced
in area. Do not describe it as YOLO-based emergency detection.

Two things were learned the hard way and must not be undone:

- Testing only "are red and blue both present?" flags every blue car (they have
  red tail lights). Measured: it fired on 675 of 2233 ordinary detections.
- Requiring the colours be *adjacent* does not help either — tail lights touch
  the bodywork. Only **relative area** separates the cases.

It also misses fire engines (red bodywork swamps the balance test) and has been
validated only on synthetic footage. Replacing it with a fine-tuned YOLO model
is the highest-value next step for the vision half, and touches only this file —
nothing downstream cares how `Detection.is_emergency` was set.
