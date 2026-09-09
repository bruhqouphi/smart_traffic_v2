# UML and System Diagrams

Source diagrams for the project report, Chapter Three §3.7 (System Design Tools)
and Chapter Four §4.2 / §4.5 (Architecture and Module Design).

Every diagram is generated from the code as it actually stands, not from the
proposal. Where the two disagree, the code wins and the divergence is noted.

Render these with any Mermaid renderer (mermaid.live, VS Code Markdown Preview
Mermaid, or the published artifact) and export as PNG/SVG for the report.

---

## 3.7.1 Use Case Diagram

Note there is no "motorist" actor. Drivers never interact with this system —
they are the *subject* of measurement, not users of the software. The
emergency vehicle appears as a passive trigger, not an operator.

```mermaid
flowchart LR
    RES(["Researcher"])
    OPR(["Demo Operator"])
    VID(["Video Source"])
    EV(["Emergency Vehicle"])

    subgraph SYS["Smart Traffic Signal Control System"]
        direction TB
        UC1(["Run single simulation"])
        UC2(["Compare algorithms<br/>across scenarios"])
        UC3(["Sweep aging bound"])
        UC4(["Sweep preemptive<br/>scheduling"])
        UC5(["Generate synthetic<br/>footage"])
        UC6(["Evaluate detection<br/>accuracy"])
        UC7(["Run live dashboard"])
        UC8(["Hot-swap algorithm<br/>mid-demo"])
        UC9(["Detect and count<br/>vehicles"])
        UC10(["Classify emergency<br/>vehicle"])
        UC11(["Preempt signal"])
        UC12(["Export metrics<br/>to CSV"])
    end

    RES --> UC1
    RES --> UC2
    RES --> UC3
    RES --> UC4
    RES --> UC5
    RES --> UC6
    OPR --> UC7
    OPR --> UC8
    VID --> UC7
    EV -.triggers.-> UC10

    UC2 -.includes.-> UC1
    UC2 -.includes.-> UC12
    UC3 -.includes.-> UC1
    UC4 -.includes.-> UC1
    UC7 -.includes.-> UC9
    UC9 -.includes.-> UC10
    UC10 -.extends.-> UC11
    UC6 -.includes.-> UC9
```

---

## 3.7.2 Class Diagram — Signal Control

The central design decision in the project. `PreemptiveSchedulingController`
and `EmergencyPreemptionController` are **decorators**: each *is* a
`TimingAlgorithm` and *holds* a `TimingAlgorithm`. That is why emergency
preemption is not a fifth algorithm — it composes over any of the four.

`build_controller()` composes them in a fixed order, `base → preemptive →
emergency`, with emergency outermost so an ambulance can never be interrupted
by the mid-green scheduler.

```mermaid
classDiagram
    direction TB

    class TimingAlgorithm {
        <<abstract>>
        +next_phase(queues, current_phase, elapsed) str
        +green_duration(queues, phase) float
        +get_last_reason() str
        +update_sim_time(t)
        +record_served(phase)
        +wants_preemption(queues, phase, elapsed) bool
    }

    class FixedTimingAlgorithm {
        -green_time: float
        +next_phase() str
        +green_duration() float
    }

    class ProportionalTimingAlgorithm {
        -min_green: float
        -max_green: float
        +green_duration() float
    }

    class QueueClearingAlgorithm {
        -threshold: int
        -max_wait: float
        -_last_served: dict
        +_is_starving(phase) bool
        +next_phase() str
        +green_duration() float
    }

    class LongestQueueFirstAlgorithm {
        +next_phase() str
    }

    class PreemptiveSchedulingController {
        -base: TimingAlgorithm
        -min_service: float
        -margin: int
        +wants_preemption() bool
    }

    class EmergencyPreemptionController {
        -base: TimingAlgorithm
        -min_green_before_preempt: float
        -max_preempt_green: float
        -clearance_extension: float
        +is_preempting bool
        +target_phase str
        +notify_emergency(phases, current) bool
    }

    TimingAlgorithm <|-- FixedTimingAlgorithm
    TimingAlgorithm <|-- ProportionalTimingAlgorithm
    TimingAlgorithm <|-- QueueClearingAlgorithm
    QueueClearingAlgorithm <|-- LongestQueueFirstAlgorithm
    TimingAlgorithm <|-- PreemptiveSchedulingController
    TimingAlgorithm <|-- EmergencyPreemptionController

    PreemptiveSchedulingController o-- TimingAlgorithm : wraps base
    EmergencyPreemptionController o-- TimingAlgorithm : wraps base

    class PhaseManager {
        -state: SignalState
        -current_phase: str
        +request_phase_change(phase, green)
        +truncate_green(min_elapsed) bool
        +hold_green(duration)
        +step(dt) bool
        +get_signal_colors() dict
    }

    class SignalState {
        <<enumeration>>
        GREEN
        YELLOW
        ALL_RED
    }

    PhaseManager --> SignalState : holds
```

---

## 3.7.3 Class Diagram — Simulation Pipeline

The pipeline behind every result in the report. `SimEngine` owns the model;
the controller is injected, which is what makes a four-way comparison possible
without touching the model.

```mermaid
classDiagram
    direction TB

    class SimEngine {
        -config: dict
        -algorithm: TimingAlgorithm
        +step()
        +run(duration) MetricsCollector
        +get_state() dict
        -_service_emergency()
        -_service_scheduler_preemption()
        -_is_discharging() bool
    }

    class Intersection {
        -queues: dict
        +arrive(arrivals, t) dict
        +arrive_emergency(approaches, t) list
        +depart_phase(phase, dt, t) list
        +queue_lengths() dict
        +clearance_time(phase) float
        +emergency_phases() set
    }

    class ApproachQueue {
        -capacity: int
        -vehicles: list
        +arrive(n, t, movements) int
        +arrive_emergency(t) Vehicle
        +depart(dt, t) list
        +service_time(vehicle) float
        +is_full() bool
    }

    class Vehicle {
        +arrival_time: float
        +departure_time: float
        +movement: str
        +is_emergency: bool
        +wait_time() float
    }

    class TurningMix {
        -through: float
        -left: float
        -right: float
        +sample(n) list
        +adjustment(movement) float
    }

    class TrafficGenerator {
        -rates: dict
        -rng: Generator
        -ev_rng: Generator
        +arrivals_all(dt) dict
        +emergency_arrivals(dt) list
    }

    class MetricsCollector {
        +record_queue_snapshot(t, queues)
        +record_vehicle_wait(wait, approach)
        +record_emergency_clearance(vehicle)
        +record_preemption(t, phase)
        +summary() dict
        +export_csv(dir, prefix) dict
    }

    SimEngine *-- Intersection
    SimEngine *-- TrafficGenerator
    SimEngine *-- MetricsCollector
    SimEngine *-- PhaseManager
    SimEngine o-- TimingAlgorithm : injected
    Intersection *-- ApproachQueue
    Intersection *-- TurningMix
    ApproachQueue *-- Vehicle
```

---

## 3.7.4 Class Diagram — Detection Pipeline

Separate from the simulation entirely. Both detectors satisfy the same
implicit interface — `detect(frame) -> List[Detection]` — so the dashboard
swaps between YOLO and the colour detector without knowing which it holds.

`EmergencyClassifier` is deliberately a separate collaborator rather than part
of either detector: COCO has no ambulance class, so emergency status is
decided *after* detection, by light-bar heuristic.

```mermaid
classDiagram
    direction TB

    class VideoInput {
        -frame_skip: int
        -loop: bool
        +read() ndarray
        +get_first_frame() ndarray
        +release()
    }

    class Detection {
        +x1: float
        +y1: float
        +x2: float
        +y2: float
        +confidence: float
        +class_id: int
        +class_name: str
        +is_emergency: bool
        +center() tuple
        +bbox() tuple
    }

    class VehicleDetector {
        -model: YOLO
        -confidence_threshold: float
        +detect(frame) list
    }

    class ColorDetector {
        -min_area: int
        -min_saturation: int
        -min_value: int
        +from_config(config) ColorDetector
        +detect(frame) list
    }

    class EmergencyClassifier {
        -min_lightbar_fraction: float
        -max_lightbar_fraction: float
        -min_lightbar_balance: float
        -max_fixture_extent: float
        +is_emergency(frame, det) bool
        +classify(frame, detections) list
    }

    class ROIManager {
        -rois: dict
        +count_vehicles_per_approach(dets) dict
        +emergency_approaches(dets) set
        +from_file(path) ROIManager
    }

    class Dashboard {
        -detector
        -algorithm: TimingAlgorithm
        +run()
        -_process_frame()
        -_service_emergency()
        -_switch_algorithm(idx)
    }

    VehicleDetector ..> Detection : creates
    ColorDetector ..> Detection : creates
    VehicleDetector o-- EmergencyClassifier
    ColorDetector o-- EmergencyClassifier
    EmergencyClassifier ..> Detection : sets is_emergency
    ROIManager ..> Detection : reads center
    Dashboard *-- VideoInput
    Dashboard o-- ROIManager
    Dashboard o-- TimingAlgorithm
    Dashboard *-- PhaseManager
```

---

## 3.7.5 Sequence Diagram — Emergency Vehicle Preemption

One simulation tick in which an ambulance arrives on a red approach. This is
the mechanism behind the 78–86% response-time reduction.

Note `truncate_green` rather than an instant switch: a running green must
serve `min_green_before_preempt` seconds before it can be cut, which is what
real EVP controllers do. Preemption skips the *wait*, never the clearance.

```mermaid
sequenceDiagram
    autonumber
    participant TG as TrafficGenerator
    participant EN as SimEngine
    participant IN as Intersection
    participant EP as EmergencyPreemption<br/>Controller
    participant BA as Base algorithm
    participant PM as PhaseManager
    participant MC as MetricsCollector

    EN->>TG: emergency_arrivals(dt)
    TG-->>EN: ["east"]
    EN->>IN: arrive_emergency(["east"], t)
    IN-->>EN: Vehicle(is_emergency=True)

    Note over EN: _service_emergency()
    EN->>IN: emergency_phases()
    IN-->>EN: {"EW"}
    EN->>EP: notify_emergency({"EW"}, current="NS")
    EP-->>EN: preempting = True

    alt current phase is not the target
        EN->>PM: request_phase_change("EW", max_preempt_green)
        EN->>PM: truncate_green(min_green_before_preempt)
        PM-->>EN: green cut short
    else already serving the target
        EN->>PM: hold_green(max_preempt_green)
    end
    EN->>MC: record_preemption(t, "EW")

    loop each tick while EW is green
        EN->>IN: depart_phase("EW", dt, t)
        IN-->>EN: [departed vehicles]
        EN->>MC: record_emergency_clearance(vehicle)
    end

    Note over EP: EV clear — hold target green<br/>for clearance_extension seconds
    EP->>EP: release preemption
    EN->>BA: next_phase(queues, current, t)
    BA-->>EN: normal control resumes
```

---

## 3.7.6 Activity Diagram — Phase Selection

Drawn for both adaptive controllers at once, because the comparison *is* the
finding. The two rules share every gate except the final one, shaded below.

Under a tight aging bound the first gate fires on nearly every decision, so
the divergent node is rarely reached — which is why `queue_clearing` and
`longest_queue_first` produce identical results at `max_wait_threshold: 20`.
The diagram shows a phase-selection problem that has already been decided
before the selection rule is consulted.

```mermaid
flowchart TD
    START(["Phase boundary reached"]) --> AGE{"Other phase starved?<br/>time since served exceeds max_wait"}
    AGE -->|yes| PROMOTE["Serve the starved phase<br/><i>reason: Aging</i>"]
    AGE -->|no| BOTH{"Both queues empty?"}
    BOTH -->|yes| ALT["Alternate phase<br/><i>reason: Both empty</i>"]
    BOTH -->|no| ONE{"Exactly one queue empty?"}
    ONE -->|yes| NONEMPTY["Serve the non-empty phase"]
    ONE -->|no| RULE{"Selection rule"}

    RULE -->|queue_clearing / SJF| SJF{"Either queue<br/>≤ threshold?"}
    SJF -->|yes| SHORT["Serve the shorter queue<br/><i>reason: SJF</i>"]
    SJF -->|no| LARGER1["Serve the larger queue"]
    RULE -->|longest_queue_first| LARGER2["Serve the larger queue<br/><i>max-pressure</i>"]

    PROMOTE --> GREEN
    ALT --> GREEN
    NONEMPTY --> GREEN
    SHORT --> GREEN
    LARGER1 --> GREEN
    LARGER2 --> GREEN

    GREEN{"Queue ≤ threshold?"} -->|yes| SG["green = short_green"]
    GREEN -->|no| LG["green = startup_lost + q × headway<br/>clamped to long_min…long_max"]
    SG --> END(["Apply green time"])
    LG --> END

    style RULE fill:#e8a33d,stroke:#b87d20,color:#1a1a1a
    style SJF fill:#f3d9ae,stroke:#b87d20,color:#1a1a1a
    style SHORT fill:#f3d9ae,stroke:#b87d20,color:#1a1a1a
    style LARGER1 fill:#f3d9ae,stroke:#b87d20,color:#1a1a1a
    style LARGER2 fill:#f3d9ae,stroke:#b87d20,color:#1a1a1a
    style AGE fill:#2e7d5b,stroke:#1c5138,color:#ffffff
```

---

## 3.7.7 Data Flow Diagram — Level 0 (Context)

The system has two independent input paths that never meet. Keeping them
separate on the page prevents the most common misreading of this project —
that video drives the experimental results. It does not.

```mermaid
flowchart LR
    RES["Researcher"]
    OPR["Demo Operator"]
    CAM["Video file /<br/>camera feed"]

    SYS(("Smart Traffic<br/>Signal Control<br/>System"))

    CSV["Results<br/>CSV + charts"]
    SCR["Live dashboard<br/>display"]

    RES -->|scenario, algorithm,<br/>trials, seed| SYS
    OPR -->|algorithm hot-swap<br/>keys 1–4| SYS
    CAM -->|video frames| SYS
    SYS -->|wait, queue, throughput,<br/>blocked, EV response| CSV
    SYS -->|signal state, counts,<br/>EV alerts| SCR
```

## 3.7.8 Data Flow Diagram — Level 1

```mermaid
flowchart TB
    subgraph EXP["Experimental pipeline — produces all reported results"]
        direction LR
        P1(("1.0<br/>Generate<br/>arrivals"))
        P2(("2.0<br/>Model<br/>queues"))
        P3(("3.0<br/>Select phase<br/>and green"))
        P4(("4.0<br/>Collect<br/>metrics"))
        P1 -->|arrivals per approach| P2
        P2 -->|queue lengths| P3
        P3 -->|phase, green duration| P2
        P2 -->|waits, departures, blocked| P4
    end

    subgraph VIS["Vision pipeline — live demonstration"]
        direction LR
        P5(("5.0<br/>Read<br/>frames"))
        P6(("6.0<br/>Detect<br/>vehicles"))
        P7(("7.0<br/>Classify<br/>emergency"))
        P8(("8.0<br/>Count per<br/>ROI"))
        P9(("9.0<br/>Select phase<br/>and green"))
        P5 -->|frame| P6
        P6 -->|detections| P7
        P7 -->|flagged detections| P8
        P8 -->|counts per approach| P9
    end

    D1[("config/*.yaml")]
    D2[("config/synthetic_roi.json")]
    D3[("data/videos/*.mp4")]
    D4[("results/*.csv")]
    D5[("ground truth JSON")]

    D1 -.->|rates, timing,<br/>turning, capacity| P1
    D1 -.->|thresholds| P3
    D1 -.->|thresholds| P9
    D1 -.->|detector params| P6
    D2 -.->|lane polygons| P8
    D3 -.->|frames| P5
    P4 -->|per-run metrics| D4
    D5 -.->|labelled boxes| EVAL(("10.0<br/>Score<br/>detection"))
    P6 -->|detections| EVAL
    EVAL -->|precision, recall, F1,<br/>count MAE| D4
```

---

## Divergences from the proposal

Recorded here so Chapter Three can state them explicitly rather than leaving a
reader to notice the gap.

| Proposal said | System does | Where to address it |
|---|---|---|
| Six modules including an IoT interface | Five modules; IoT not built | §1.6 Scope, §5.6 Future Work |
| YOLOv8 classifies emergency vehicles | Light-bar colour heuristic, applied after detection | §3.7.4, §4.5, §5.2 |
| One "comprehensive adaptive algorithm" | Four comparable controllers plus two decorators | §3.5, §4.5 |
| Single video-driven pipeline | Two independent pipelines | §4.2, §3.7.7 |
| — | Aging bound governs phase selection | §4.10 Results — this is the headline finding |
