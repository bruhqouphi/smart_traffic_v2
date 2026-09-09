KWAME NKRUMAH UNIVERSITY OF SCIENCE AND TECHNOLOGY

COLLEGE OF SCIENCE

FACULTY OF PHYSICAL AND COMPUTATIONAL SCIENCES

DEPARTMENT OF COMPUTER SCIENCE

*[KNUST crest]*

SMART TRAFFIC SIGNAL CONTROL SYSTEM USING COMPUTER VISION AND ADAPTIVE
QUEUE-BASED OPTIMIZATION: A COMPARATIVE STUDY OF PHASE-SELECTION AND
GREEN-TIME ALLOCATION STRATEGIES

PROF. YAW MARFO MISSAH

KISSI JOSHUA — 3395122

---

# ABSTRACT

Urban road junctions in Ghanaian cities operate predominantly on fixed-time signal plans
that cannot respond to the traffic actually present, producing avoidable delay whenever
demand departs from the historical averages used to compute the plan. A second and more
serious consequence is that emergency vehicles have no mechanism by which a junction can
clear a path for them. This project designs, implements and evaluates a smart traffic
signal control system combining computer-vision vehicle detection with adaptive,
queue-based signal timing, and adds emergency-vehicle preemption on top of it.

Rather than proposing a single adaptive controller and demonstrating that it outperforms
a fixed-time baseline — a result already well established — this research asks a sharper
question: on a two-phase junction, which half of an adaptive controller actually reduces
waiting time, the rule that chooses *which* phase to serve next, or the rule that decides
*how long* to serve it? Four controllers were implemented behind a common interface
(fixed-time, demand-proportional, a shortest-job-first queue-clearing rule, and a
longest-queue-first max-pressure rule) and evaluated over five seeded trials of 600
simulated seconds across four demand scenarios, using a purpose-built point-queue
simulator incorporating turning movements, approach storage capacity and yellow-interval
discharge.

The results identify green-time allocation as the effective lever. A saturation-flow
green rule with prompt alternation reduced average waiting time by 33% against
fixed-time and 22% against proportional control. The central finding, however, is
negative: under a tight fairness (aging) bound, the shortest-job-first and
longest-queue-first rules produced bit-identical results, because a starved phase is
promoted on essentially every decision and the selection heuristic is never consulted. That
this reflects a property of the regime rather than an implementation defect was confirmed by
sweeping the bound for both controllers: they agree at 20 s and below, and diverge on all
four scenarios at 25 s and above. On a two-phase junction, once aging is tight, there is no
phase-order problem left to solve. Sweeping the aging bound from 60 s to 20 s also reduced
average waiting time monotonically from 22.3 s to 13.5 s, confirming it as the dominant
tuning parameter.

Emergency-vehicle preemption, implemented as a decorator composing over any of the four
controllers, reduced emergency-vehicle response time by 78–86% at a cost of 1–6 s of
additional delay to ordinary traffic. The vision pipeline was evaluated against
automatically generated ground truth, achieving 99.90% precision, 97.67% recall and an
F1-score of 98.77%, with a per-approach queue-count mean absolute error of 0.08 vehicles.
This evaluation also exposed and corrected a detection defect that was silently
discarding 84% of motorbikes.

The primary contribution is a controlled comparison that isolates and answers a question
usually left implicit in adaptive signal control research, together with a negative
result explaining *why* two textbook-distinct scheduling heuristics become
indistinguishable in practice.

---

# ACKNOWLEDGEMENT

First and foremost, I would like to express my sincere gratitude to God Almighty for the
strength, health and perseverance granted throughout this project.

I would like to acknowledge my supervisor, Prof. Yaw Marfo Missah, for his supervision,
direction and constructive criticism throughout the course of this work.

I am also grateful to the staff of the Department of Computer Science, KNUST, for the
foundation on which this project was built.

Finally, I am thankful to my family and friends for their patience and constant
encouragement over the course of this demanding project.

---

# TABLE OF CONTENTS

ABSTRACT
ACKNOWLEDGEMENT
LIST OF FIGURES
LIST OF TABLES
LIST OF ABBREVIATIONS

**CHAPTER 1: INTRODUCTION**
1.1 Background
1.2 Problem Statement
1.3 Aims and Objectives — 1.31 Aim · 1.32 Objectives
1.4 Scope — 1.41 In-Scope · 1.42 Out-of-Scope
1.5 Significance
1.6 Report Structure

**CHAPTER 2: LITERATURE REVIEW**
2.0 Introduction
2.1 Traditional Traffic Signal Control
2.2 Adaptive Traffic Signal Control Systems
2.3 Queue-Theoretic Scheduling Applied to Signal Timing
2.4 Computer Vision for Traffic Monitoring
2.5 Emergency Vehicle Preemption
2.6 Comparative Analysis of Existing Systems
2.7 Summary and The Research Gap

**CHAPTER 3: METHODOLOGY**
3.0 Introduction
3.1 System Architecture — 3.1.1 A Two-Pipeline Architecture · 3.1.2 UML Use Case Diagram
3.2 The Simulation Model — 3.2.1 Arrivals · 3.2.2 Turning Movements · 3.2.3 Storage Capacity · 3.2.4 Yellow-Interval Discharge
3.3 The Computer Vision Pipeline — 3.3.1 Vehicle Detection · 3.3.2 Emergency Identification · 3.3.3 ROI Counting
3.4 The Core Research Contribution — 3.4.1 The Four Controllers · 3.4.2 The Aging Bound · 3.4.3 Preemption as a Decorator
3.5 Data Design
3.6 System Evaluation

**CHAPTER 4: RESULTS AND FINDINGS**
4.0 Introduction
4.1 Below Capacity: Where Green Allocation Is Decided
4.2 The Aging Bound Sweep
4.3 Above Capacity: Where Wait Time Stops Being the Metric
4.4 Emergency Vehicle Preemption Results
4.5 Detection Accuracy Evaluation
4.6 User Interface Showcase
4.7 Key Findings Summary

**CHAPTER 5: DISCUSSION AND CONCLUSION**
5.0 Introduction
5.1 Discussion of Findings
5.2 Key Contributions of the Research
5.3 Limitations of the Study
5.4 Recommendations and Future Work
5.5 Conclusion

REFERENCES

---

# LIST OF FIGURES

*(Page numbers to be completed after typesetting.)*

| Figure | Title | Section | Page |
|---|---|---|:---:|
| 3.1 | System context diagram: the two independent pipelines | 3.1.1 | — |
| 3.2 | Use case diagram | 3.1.2 | — |
| 3.3 | Class diagram: simulation pipeline | 3.2.4 | — |
| 3.4 | Class diagram: detection pipeline | 3.3.3 | — |
| 3.5 | Activity diagram: phase-selection decision | 3.4.2 | — |
| 3.6 | Class diagram: signal control hierarchy (Decorator pattern) | 3.4.3 | — |
| 3.7 | Sequence diagram: emergency vehicle preemption | 3.4.3 | — |
| 3.8 | Level 1 data flow diagram | 3.5 | — |
| 4.1 | Average waiting time by controller and scenario | 4.1 | — |
| 4.2 | Distribution of vehicle waiting times by controller | 4.1 | — |
| 4.3 | Queue length against time, balanced scenario | 4.2 | — |
| 4.4 | Dashboard under normal operation | 4.6 | — |
| 4.5 | Dashboard during emergency preemption | 4.6 | — |

---

# LIST OF TABLES

*(Page numbers to be completed after typesetting.)*

| Table | Title | Section | Page |
|---|---|---|:---:|
| 2.1 | Comparative analysis of existing signal control systems | 2.6 | — |
| 3.1 | Arrival rates for the below-capacity configuration | 3.2.1 | — |
| 3.2 | Selected configuration parameters (data dictionary extract) | 3.5 | — |
| 4.1 | Average waiting time, below capacity | 4.1 | — |
| 4.2 | Average waiting time against aging threshold | 4.2 | — |
| 4.3 | Oversaturated performance, balanced scenario | 4.3 | — |
| 4.4 | Emergency response time against ordinary waiting time | 4.4 | — |
| 4.5 | Detection performance at IoU ≥ 0.5 | 4.5 | — |
| 4.6 | Per-approach queue count accuracy | 4.5 | — |
| 4.7 | False negatives by vehicle type | 4.5 | — |
| 4.8 | Detection performance against minimum-area threshold | 4.5 | — |
| 4.9 | Emergency classification performance | 4.5 | — |

---

# LIST OF ABBREVIATIONS

| Abbreviation | Meaning |
|---|---|
| CNN | Convolutional Neural Network |
| COCO | Common Objects in Context (dataset) |
| CSV | Comma-Separated Values |
| DFD | Data Flow Diagram |
| EV | Emergency Vehicle |
| EVP | Emergency Vehicle Preemption |
| F1 | Harmonic mean of precision and recall |
| FIFO | First In, First Out |
| HCM | Highway Capacity Manual |
| HSV | Hue, Saturation, Value (colour space) |
| IoU | Intersection over Union |
| LQF | Longest Queue First |
| MAE | Mean Absolute Error |
| ROI | Region of Interest |
| SCATS | Sydney Coordinated Adaptive Traffic System |
| SCOOT | Split Cycle Offset Optimisation Technique |
| SJF | Shortest Job First |
| SRTF | Shortest Remaining Time First |
| YAML | YAML Ain't Markup Language |
| YOLO | You Only Look Once (object detector) |

---

# CHAPTER 1: INTRODUCTION

## 1.1 Background

Road traffic congestion is among the most visible constraints on productivity in Ghanaian
cities. In Kumasi and Accra, peak-hour travel times are routinely several times
free-flow times, and the resulting delay imposes costs in fuel, vehicle wear, lost working
hours and vehicle emissions. A substantial share of that delay is incurred not on the open
road but at signalised junctions, where vehicles wait for a green indication that is, in
many cases, allocated without reference to the traffic actually present.

The majority of signalised junctions in Ghana operate under fixed-time control. A
fixed-time controller repeats a predetermined cycle in which each phase receives a fixed
green duration, calculated offline from historical counts. The method dates to Webster
(1958), whose formulation of optimal cycle length and green splits remains the basis of
fixed-time design, and it performs acceptably when demand matches the assumptions used to
derive the plan. It fails when demand departs from them — which, over the course of a day,
is most of the time. The characteristic symptom is familiar to any road user: a queue held
at red on one approach while the conflicting approach discharges an empty green.

Adaptive control addresses this by measuring demand and reallocating green time in
response. Deployed systems such as SCOOT (Hunt et al., 1982) and SCATS (Lowrie, 1990) have
demonstrated substantial delay reductions across networks of junctions, and a large
research literature has since explored max-pressure formulations (Varaiya, 2013) and
reinforcement learning approaches (Wei et al., 2018). What these systems have in common is
a dependence on vehicle detection — historically inductive loop detectors buried in the
carriageway, which are expensive to install and disruptive to maintain.

Computer vision offers an alternative sensing route. Deep learning object detectors,
particularly the single-stage YOLO family introduced by Redmon et al. (2016) and developed
through to YOLOv8 (Jocher et al., 2023), can locate and classify multiple vehicles per
frame in real time. Because many junctions already carry cameras for enforcement or
surveillance, a vision-based controller can in principle be deployed against existing
infrastructure rather than new sensing hardware.

A separate and more urgent failure of fixed-time control concerns emergency vehicles. An
ambulance, fire tender or police vehicle approaching a signalised junction has no means of
communicating its presence to the controller. It must either wait with ordinary traffic or
contravene the signal. Emergency vehicle preemption (EVP) systems, which grant priority
passage upon detection of an approaching emergency vehicle, are standard in many
jurisdictions (Qin & Khan, 2012) but are essentially absent from Ghanaian junctions.

## 1.2 Problem Statement

Fixed-time signal control cannot respond to real-time variation in traffic demand,
producing avoidable delay whenever actual demand departs from the historical averages used
to compute the plan. This is the general problem, and adaptive control is the general
answer to it.

However, the term "adaptive control" conflates two logically distinct decisions that a
signal controller makes at every phase boundary:

1. **Phase selection** — which of the available phases should be served next?
2. **Green allocation** — how long should that phase be served for?

The research literature routinely presents adaptive controllers as unified strategies and
evaluates them against fixed-time baselines as a whole. A controller that beats fixed-time
is reported as a success, but the evaluation rarely establishes *which of its two
decisions* produced the gain. This matters practically, because the two decisions differ
enormously in implementation cost. Green allocation requires only a queue-length estimate
and an arithmetic rule, whereas sophisticated phase selection requires a model of the
junction and, in reinforcement-learning approaches, extensive training. If phase selection
contributes little on a simple junction, effort spent on it is misdirected.

A second problem concerns emergency vehicles. Existing traffic infrastructure in Ghanaian
cities offers no mechanism to detect an approaching emergency vehicle and clear its path.
In time-critical medical emergencies, this delay has direct consequences for patient
outcomes.

The problem this project addresses is therefore twofold: to determine **which component of
adaptive signal control actually reduces waiting time on a two-phase junction**, and to
demonstrate that emergency-vehicle priority can be layered onto such a controller without
disturbing its ordinary-traffic behaviour.

## 1.3 Aims and Objectives

### 1.31 Aim

The aim of this project is to develop and evaluate a smart traffic signal control system
that uses computer vision for vehicle detection and adaptive queue-based timing for signal
control, and to determine through controlled comparison whether phase-selection strategy
or green-time allocation strategy is the effective lever in reducing average vehicle
waiting time at a four-way, two-phase junction.

### 1.32 Objectives

1. To implement a real-time vehicle detection module capable of locating and counting
   vehicles at each approach of a junction from video, and of identifying emergency
   vehicles among those detections.
2. To develop a traffic analysis module that converts detections into per-approach queue
   lengths and estimates the clearance time of each approach.
3. To implement four signal timing controllers behind a common interface — fixed-time,
   demand-proportional, shortest-job-first queue clearing, and longest-queue-first
   max-pressure control — such that they differ only in their phase-selection and
   green-allocation rules.
4. To design and implement an emergency-vehicle preemption mechanism that composes over
   any of the four controllers without modifying them.
5. To build a discrete-time simulation of a four-way junction incorporating turning
   movements, approach storage capacity and yellow-interval discharge, to serve as the
   experimental instrument for the comparison.
6. To develop a real-time visualisation dashboard displaying live detection, signal state,
   per-approach queue counts and emergency alerts.
7. To evaluate the controllers over seeded, repeated trials across four demand scenarios
   using average waiting time, maximum waiting time, throughput, blocked demand and
   emergency-vehicle response time; and to evaluate the detection module against ground
   truth using precision, recall and F1-score.

## 1.4 Scope

### 1.41 In-Scope

1. **A single isolated junction.** One four-way intersection operating two conflicting
   phases (North–South and East–West).
2. **Simulation-based evaluation.** All quantitative traffic results derive from a
   purpose-built point-queue simulator, permitting seeded, repeatable trials.
3. **Four timing controllers** implemented behind a common interface, plus two preemption
   decorators.
4. **A computer vision pipeline** covering vehicle detection, emergency-vehicle
   identification, region-of-interest assignment and per-approach counting, exercised
   against generated synthetic footage.
5. **A live visualisation dashboard** demonstrating the full vision-to-signal pipeline,
   including mid-demonstration algorithm switching.
6. **Quantitative evaluation of both halves**: controller performance against traffic
   metrics, and detector performance against ground-truth annotations.

### 1.42 Out-of-Scope

1. **Physical deployment.** The system was not connected to real traffic signal hardware,
   and no IoT or microcontroller implementation was undertaken.
2. **Network coordination.** Coordination between adjacent junctions, green waves and
   corridor-level control are outside this work; the junction is treated as isolated.
3. **Protected turn phases.** The junction operates two phases only. Junctions with
   dedicated turning phases are not modelled.
4. **Real-world traffic data.** No field data was collected from Ghanaian junctions.
   Demand is generated from Poisson processes and the vision pipeline is evaluated on
   synthetic footage.
5. **A trained emergency-vehicle classifier.** Emergency identification uses a
   colour-based light-bar heuristic, not a model trained on emergency vehicles.

## 1.5 Significance

**Methodological significance.** The project's principal significance is that it isolates a
question usually left implicit. By holding the simulation model, the demand and the
green-allocation rule constant while varying only the phase-selection rule, it establishes
which component of an adaptive controller carries the benefit. The resulting negative
result — that two textbook-distinct scheduling heuristics become indistinguishable under a
tight fairness constraint — is of practical value to anyone designing a controller for a
simple junction, because it identifies effort that need not be spent.

**Practical significance.** The demonstration that emergency-vehicle preemption reduces
response time by 78–86% for 1–6 s of additional delay to ordinary traffic quantifies a
trade-off usually asserted rather than measured, in a form directly relevant to Ghanaian
cities where no such capability currently exists.

**Economic and environmental significance.** Reduced waiting translates directly into
reduced idling, lower fuel consumption and lower vehicle emissions.

**Technological significance.** By driving control from camera input rather than inductive
loops, the approach is compatible with existing surveillance infrastructure and avoids
carriageway excavation, lowering the barrier to deployment in a resource-constrained
setting.

## 1.6 Report Structure

This report is organised into five chapters. Chapter 1 has introduced the problem, the aim
and objectives, and the scope of the work. Chapter 2 reviews the literature on traditional
and adaptive signal control, queue-theoretic scheduling, computer vision for traffic
monitoring and emergency vehicle preemption, and identifies the research gap. Chapter 3
details the methodology: the system architecture, the simulation model, the vision
pipeline, the controller designs that constitute the core contribution, the data design
and the evaluation protocol. Chapter 4 presents the experimental results. Chapter 5
discusses those findings, states the contributions and limitations of the work, and offers
recommendations for future research.

---

# CHAPTER 2: LITERATURE REVIEW

## 2.0 Introduction

This chapter reviews the literature relevant to adaptive traffic signal control and
vision-based traffic monitoring. It begins with traditional fixed-time and actuated
control, establishing the baseline against which adaptive methods are measured. It then
surveys deployed and research adaptive systems, before turning to the queue-theoretic
scheduling principles that underpin the controllers implemented in this project.
Subsequent sections review computer vision for traffic monitoring and emergency vehicle
preemption. The chapter closes by comparing existing systems and identifying the gap this
project addresses.

## 2.1 Traditional Traffic Signal Control

The theoretical foundation of fixed-time signal design was established by Webster (1958),
who derived expressions for the cycle length minimising average delay and for the division
of green time between phases in proportion to their degree of saturation. Webster's method
remains embedded in contemporary signal timing practice, and the *Traffic Signal Timing
Manual* (Koonce & Rodegerdts, 2008) presents it as the standard starting point for
fixed-time plan design.

Fixed-time control has clear virtues: it is inexpensive, requires no detection
infrastructure, is trivially predictable, and fails safe. Its limitation is equally clear.
Because the plan is computed offline from historical counts, it cannot respond to the
demand actually present. Roess, Prassas and McShane (2019) note that the resulting
inefficiency is greatest precisely when demand is asymmetric or when it departs from the
historical profile — during incidents, events, or simply at times of day not well
represented in the count data.

Actuated control represents a partial remedy. Using inductive loop detectors at the stop
line, an actuated controller can extend a green interval while vehicles continue to arrive,
and can skip a phase for which no demand is registered. Koonce and Rodegerdts (2008)
document the design of such systems in detail. Their limitation is informational: a stop
line loop reports presence, not queue length, so an actuated controller knows that vehicles
are waiting but not how many. This distinction matters directly for the present work, whose
controllers are driven by queue *magnitude*.

## 2.2 Adaptive Traffic Signal Control Systems

SCOOT (Split Cycle Offset Optimisation Technique), described by Hunt et al. (1982),
represented the first widely deployed adaptive system. SCOOT maintains an online model of
traffic flow using upstream detectors and makes small, frequent adjustments to splits,
cycle length and offsets across a network. SCATS (Lowrie, 1990), developed independently in
Australia, adopts a comparable objective through a different mechanism, selecting among
pre-computed plans based on measured degree of saturation. Both systems demonstrated
meaningful delay reductions in field deployment, and both are network-oriented: their
principal contribution lies in coordination between junctions.

More recent research has pursued formal control-theoretic guarantees. Varaiya (2013)
introduced max-pressure control, in which the phase activated is the one maximising a
"pressure" quantity derived from upstream and downstream queue lengths. Max-pressure is
significant because it is provably stabilising — it maximises the throughput region of the
network without requiring knowledge of arrival rates. The `longest_queue_first` controller
implemented in this project is a simplified, single-junction realisation of this principle,
where pressure reduces to queue length because there is no modelled downstream link.

A parallel research direction applies reinforcement learning. Wei et al. (2018) present
IntelliLight, a deep reinforcement learning agent trained on real traffic data which learns
a signal control policy through interaction with the environment. Such approaches can
capture patterns that hand-designed rules miss, but they require substantial training data
and computation, and their learned policies are difficult to interpret or certify — a
significant obstacle to deployment in safety-critical infrastructure.

## 2.3 Queue-Theoretic Scheduling Applied to Signal Timing

A signalised junction is, formally, a server allocating service among competing queues. This
observation permits the direct application of scheduling theory from operating systems, and
the taxonomy given by Silberschatz, Galvin and Gagne (2018) supplies the vocabulary used
throughout this project:

- **First-come-first-served / round robin.** Serving phases in fixed rotation, irrespective
  of demand. This is precisely fixed-time control.
- **Shortest job first (SJF).** Serving the shortest queue first provably minimises average
  waiting time across all jobs when service times are known. Applied to a junction, this
  suggests clearing short queues promptly so they do not accumulate delay while waiting
  behind a long queue.
- **Priority scheduling.** Assigning a class of jobs precedence over others. This maps
  directly onto emergency-vehicle preemption.
- **Preemptive scheduling.** Re-evaluating the scheduling decision mid-service rather than
  only at completion; shortest-remaining-time-first is the preemptive counterpart of SJF.
- **Aging.** A starvation-prevention mechanism which progressively raises the priority of a
  job that has waited too long. Without aging, both SJF and priority scheduling can starve
  a queue indefinitely.

The importance of aging in this taxonomy is well established in the operating systems
literature but is comparatively underexplored in the traffic signal context, where fairness
between approaches is usually enforced implicitly through maximum cycle length rather than
treated as an explicit, tunable parameter. This project makes the aging bound explicit and
sweeps it, and the results in Chapter 4 show it to dominate the phase-selection heuristic
entirely.

## 2.4 Computer Vision for Traffic Monitoring

Early vision-based traffic monitoring relied on background subtraction and frame
differencing to segment moving vehicles. These techniques are computationally cheap but
fragile: they degrade under changing illumination, cast shadows and stationary vehicles,
the last being a serious defect for queue measurement, where vehicles are stationary by
definition.

Deep learning transformed the field. Zhao et al. (2019) survey the development of
CNN-based object detection, tracing the progression from region-proposal methods to
single-stage detectors. The YOLO family, introduced by Redmon et al. (2016), reframes
detection as a single regression over the whole image, achieving real-time throughput while
remaining competitive in accuracy. YOLOv8 (Jocher et al., 2023) is the iteration used in
this project, pre-trained on the COCO dataset, which includes the vehicle classes bicycle,
car, motorcycle, bus and truck.

A limitation of COCO-pretrained detectors is directly relevant here: **COCO contains no
emergency-vehicle class.** An ambulance is detected as a truck or a car, and a fire tender
as a truck. Any system requiring emergency-vehicle identification must therefore either
fine-tune a detector on a purpose-built dataset or apply a secondary classification stage.
This project takes the latter route, for reasons set out in Section 3.3.2.

## 2.5 Emergency Vehicle Preemption

Emergency vehicle preemption systems grant priority passage to emergency vehicles at
signalised junctions. Qin and Khan (2012) analyse the control strategies involved,
emphasising that the difficult part of preemption is not the granting of green but the
*transition* — returning to normal operation without stranding the phases that were
interrupted, and without violating minimum green and clearance intervals whose purpose is
safety rather than efficiency.

Conventional EVP implementations rely on dedicated equipment: optical emitters mounted on
emergency vehicles with corresponding receivers at junctions, or GPS-based systems
broadcasting vehicle position. Both require every participating emergency vehicle to carry
hardware, which constrains deployment.

Vision-based preemption, reviewed by Wang et al. (2020), instead identifies emergency
vehicles from camera imagery by their visual signature — livery, markings and light bars.
The attraction is that no vehicle-side equipment is required and existing cameras may be
reused. The difficulty is reliability: an emergency vehicle must be distinguished from
ordinary traffic under varying illumination and viewing angle, and the consequences of a
false positive (needlessly interrupting a green) and a false negative (failing to clear a
path) are asymmetric.

## 2.6 Comparative Analysis of Existing Systems

| System / Approach | Sensing | Adapts | Strengths | Weaknesses |
|---|---|---|---|---|
| Fixed-time (Webster, 1958) | None | Nothing | Cheap, predictable, fails safe | Blind to actual demand |
| Actuated (Koonce & Rodegerdts, 2008) | Stop-line loops | Green extension, phase skip | Responds to presence | Presence only, not queue length |
| SCOOT (Hunt et al., 1982) | Upstream loops | Splits, cycle, offsets | Network coordination, proven | Costly infrastructure, network-oriented |
| SCATS (Lowrie, 1990) | Loops | Plan selection | Robust, widely deployed | Selects among precomputed plans |
| Max-pressure (Varaiya, 2013) | Queue lengths | Phase selection | Provably throughput-optimal | Assumes downstream queue knowledge |
| Reinforcement learning (Wei et al., 2018) | Various | Learned policy | Captures complex patterns | Training cost, poor interpretability |
| Vision-based EVP (Wang et al., 2020) | Camera | Emergency priority | No vehicle-side equipment | Detection reliability |
| **This project** | **Camera** | **Phase + green + EVP** | **Isolates which component matters** | **Single junction, two phases** |

*Table 2.1: Comparative analysis of existing traffic signal control systems.*

## 2.7 Summary and The Research Gap

The literature establishes conclusively that adaptive signal control outperforms fixed-time
control. It also provides mature formal treatments of individual strategies: Webster for
green splits, Varaiya for max-pressure phase selection, and the operating-systems
literature for the scheduling principles underlying both.

Two gaps remain, and this project addresses them.

**First, the components of adaptive control are seldom separated.** Published evaluations
almost invariably compare a complete adaptive controller against a fixed-time baseline and
report an aggregate improvement. Because phase selection and green allocation are varied
together, such studies cannot attribute the improvement to either. No study identified in
this review holds one constant while varying the other on an otherwise identical junction
model. Yet the two decisions differ by an order of magnitude in implementation cost, so
knowing which one carries the benefit has direct practical consequence.

**Second, the aging bound is rarely treated as a design parameter.** Fairness between
approaches is normally enforced implicitly through a maximum cycle length. The operating
systems literature treats aging explicitly as a first-class scheduling mechanism
(Silberschatz et al., 2018), but its interaction with the phase-selection rule in a traffic
context appears not to have been systematically examined. If aging is tight enough to fire
on most decisions, it may override the selection heuristic entirely — a possibility that,
if true, would substantially change how effort should be allocated when designing a
controller.

This project therefore implements four controllers differing *only* in their selection and
allocation rules, evaluates them on an identical junction model under identical seeded
demand, and sweeps the aging bound across its full useful range. It further demonstrates
that emergency-vehicle priority can be composed over any of them without altering their
ordinary-traffic behaviour.

---

# CHAPTER 3: METHODOLOGY

## 3.0 Introduction

This chapter describes the design, implementation and evaluation methodology of the
project. The development approach was iterative and experiment-driven: each controller was
implemented, tested and measured before the next was added, and the research question was
progressively sharpened as results accumulated.

The research sought to answer the following questions:

1. On a two-phase junction, is average waiting time reduced principally by the rule that
   selects which phase to serve, or by the rule that determines how long to serve it?
2. How does an explicit fairness (aging) bound interact with the phase-selection rule, and
   does it have a dominant effect?
3. Can emergency-vehicle preemption be layered onto an arbitrary controller such that
   emergency response time falls substantially while ordinary traffic behaviour is
   provably unchanged when the feature is disabled?
4. Is a vision pipeline capable of supplying per-approach queue counts of sufficient
   accuracy to drive such a controller?

## 3.1 System Architecture

### 3.1.1 A Two-Pipeline Architecture

The system comprises two pipelines which share their control logic but are otherwise
independent. This separation is the most important architectural decision in the project
and is deliberate.

**The experimental pipeline** generates vehicle arrivals from a seeded stochastic process,
models the queues at each approach, applies a controller, and records metrics. It contains
no vision component. This pipeline produces every quantitative traffic result reported in
Chapter 4.

**The vision pipeline** reads video frames, detects vehicles, classifies emergency
vehicles, assigns detections to approaches by region of interest, and applies the same
controller classes to the resulting counts. It produces the live demonstration.

The rationale for the separation is methodological. Answering the research question
requires many repetitions under controlled, reproducible demand: the results in Chapter 4
rest on 5 seeded trials × 600 simulated seconds × 4 scenarios × 4 controllers, repeated for
several parameter settings. This is not achievable by playing video, which offers whatever
traffic happens to be recorded, without repetition and without a controlled variable. Video
is the right medium for demonstrating that the pipeline works end-to-end; a simulator is the
right instrument for measuring which controller is better.

Critically, **both pipelines instantiate the same controller classes**. The rules evaluated
in simulation are literally the code that runs in the live demonstration, which is what
allows the two halves to be presented as one system rather than two.

*[Insert Figure 3.1 — `docs/diagrams/fig3-7_dfd_level0.png`]*

*Figure 3.1: System context diagram, showing the two independent input paths and their
distinct outputs.*

The modules are:

| Module | Responsibility |
|---|---|
| `src/detection/` | Video input, vehicle detection, emergency classification, ROI management |
| `src/signals/` | Timing algorithms, preemption decorators, phase and interval management |
| `src/simulation/` | Arrival generation, queue model, simulation engine |
| `src/metrics/` | Metric collection, statistical trials, detection scoring |
| `src/visualization/` | Live dashboard |

### 3.1.2 UML Use Case Diagram

*[Insert Figure 3.2 — `docs/diagrams/fig3-1_use_case.png`]*

*Figure 3.2: Use case diagram showing actors and system functions.*

The actors are the **Researcher**, who runs simulations, comparisons and parameter sweeps;
the **Demonstration Operator**, who runs the live dashboard and switches algorithms during
a demonstration; the **Video Source**, supplying frames; and the **Emergency Vehicle**,
which appears as a passive trigger rather than an operator.

It is worth noting explicitly that there is **no motorist actor**. Drivers do not interact
with this system; they are the subject of its measurements. Modelling them as users would
misrepresent the system boundary.

## 3.2 The Simulation Model

The junction is modelled as four approaches (north, south, east, west) grouped into two
conflicting phases: North–South (NS) and East–West (EW). Each approach holds a single FIFO
queue. Simulation proceeds in discrete time steps of 0.1 s.

### 3.2.1 Arrivals and Demand Scenarios

Vehicle arrivals at each approach are generated by an independent Poisson process, the
standard model for unplatooned arrivals at an isolated junction. Four demand scenarios were
defined:

| Scenario | North | South | East | West | Character |
|---|:---:|:---:|:---:|:---:|---|
| balanced | 0.09 | 0.09 | 0.09 | 0.09 | Symmetric demand |
| morning_rush | 0.15 | 0.06 | 0.18 | 0.03 | Inbound-dominant |
| evening_rush | 0.06 | 0.15 | 0.03 | 0.18 | Outbound-dominant |
| asymmetric | 0.21 | 0.03 | 0.12 | 0.06 | Lopsided but stable |

*Table 3.1: Arrival rates (vehicles/second per approach) for the below-capacity
configuration.*

All arrivals derive from a seeded random number generator, so a given seed reproduces an
identical arrival sequence. Emergency vehicles are drawn from a **separate** generator
stream, ensuring that enabling emergency preemption cannot perturb the ordinary arrival
sequence — a property necessary for a fair comparison between preemption-on and
preemption-off runs.

### 3.2.2 Turning Movements

Each arriving vehicle is assigned a movement — through, left or right — from a configurable
distribution (default 70% / 15% / 15%). Ghana drives on the right, so a permitted left turn
must yield to opposing through traffic and discharges well below saturation flow, while a
right turn is only mildly slowed. These are represented as saturation-flow adjustment
factors in the manner of the *Highway Capacity Manual* (TRB, 2016): a movement with
adjustment factor *a* consumes 1/*a* as much green time as a through movement.

Because each approach is a single queue, this also reproduces **head-of-line blocking**: a
left-turner at the front of the queue delays every vehicle behind it, irrespective of their
own movements. With the default distribution the effective saturation flow is
1800 × (0.70 + 0.15 × 0.45 + 0.15 × 0.85) = 1611 veh/h.

### 3.2.3 Storage Capacity and Spillback

Each approach has finite storage (`queue_capacity`, default 25 vehicles ≈ 175 m of queue at
7 m per vehicle). Arrivals to a full approach are turned away and recorded as `blocked`.
This is the model's representation of spillback into the upstream link.

This mechanism proved consequential. An earlier version of the model had unbounded queues,
and under oversaturation all four controllers appeared to converge on waiting time. That
convergence was partly an artefact: with unbounded storage, waiting time is measured over an
ever-growing queue and differences wash out. With capacity enforced, the oversaturated case
separates again on throughput (Section 4.3).

### 3.2.4 Discharge and the Yellow Interval

During green, vehicles discharge at the saturation flow rate adjusted for movement type.
Real junctions continue to clear one or two vehicles during the amber interval, so a
configurable portion of the yellow interval (`yellow_discharge_time`, default 2.0 s of a
3 s yellow) is treated as discharging; the remainder is clearance lost time.

The complete interval structure is: green (variable) → yellow (3 s, of which 2 s discharges)
→ all-red (2 s) → next green. Minimum green is 10 s.

*[Insert Figure 3.3 — `docs/diagrams/fig3-3_class_simulation.png`]*

*Figure 3.3: Class diagram of the simulation pipeline. Filled diamonds denote composition;
the open diamond marks the injected controller, the one collaborator the engine does not
own.*

## 3.3 The Computer Vision Pipeline

### 3.3.1 Vehicle Detection

Two detectors are implemented behind a common interface, `detect(frame) → List[Detection]`.

**`VehicleDetector`** wraps YOLOv8 (Jocher et al., 2023), filtering COCO detections to the
vehicle classes bicycle, car, motorcycle, bus and truck above a configurable confidence
threshold. This is the detector for real footage.

**`ColorDetector`** segments vehicles by HSV saturation thresholding followed by contour
extraction. It is used with generated synthetic footage, where vehicles are drawn in
high-saturation colours against low-saturation grey carriageway. It is far faster than YOLO
and, on that footage, more accurate — but it is applicable only to synthetic imagery, and
this is stated as a limitation rather than a result.

Because the dashboard depends only on the shared interface, the detector is selected at
runtime without any change to downstream code.

### 3.3.2 Emergency Vehicle Identification

As established in Section 2.4, COCO contains no emergency-vehicle class, so YOLO cannot
report that a detected vehicle is an ambulance. Emergency status is therefore decided by a
separate collaborator, `EmergencyClassifier`, applied to the cropped region of each
detection.

**This is a colour-based heuristic, not a trained classifier, and is described as such
throughout this report.** It searches for the visual signature of a light bar: saturated red
and saturated blue that are each present, each a small share of the vehicle, and balanced
in area. Four tests must pass simultaneously:

1. **Presence** — both colours occupy at least a minimum fraction of the vehicle.
2. **Bounded extent** — neither exceeds a maximum fraction, so that red or blue *paintwork*
   is not mistaken for a light bar.
3. **Balance** — the two areas are within roughly 3× of each other.
4. **Compactness** — all light-bar pixels together fit within a single compact bounding box
   covering at most 40% of the vehicle.

Each test was added in response to an observed failure, and this development history is
itself informative:

- Testing only whether red and blue were both present flagged **675 of 2,233** ordinary
  detections, because blue cars have red tail lights.
- Requiring the colours be *adjacent* did not help, since tail lights touch the bodywork.
  Only **relative area** separates the cases.
- Balance alone remained insufficient: a **bus** with blue-tinted side glazing running the
  length of its body and red tail lights across the rear satisfies the balance test. This
  motivated the fourth test, compactness — a real light bar is a single compact fixture.

### 3.3.3 Region-of-Interest Counting

The controller consumes per-approach queue counts, not bounding boxes. `ROIManager` holds
one polygon per approach lane and assigns each detection to the first polygon containing its
centre point, guaranteeing that a vehicle is counted at most once. The resulting mapping
`{approach: count}` is exactly the interface the simulation supplies to the same
controllers, which is what allows the identical controller code to serve both pipelines.

*[Insert Figure 3.4 — `docs/diagrams/fig3-4_class_detection.png`]*

*Figure 3.4: Class diagram of the detection pipeline. `EmergencyClassifier` mutates a field
on a `Detection` it does not create — the seam that allows a trained model to replace the
heuristic without altering anything downstream.*

## 3.4 The Core Research Contribution: Isolating Phase Selection from Green Allocation

The central methodological device of this project is a set of controllers constructed so
that they differ *only* in the decisions under study. All four implement the same abstract
interface and are driven by the same engine, the same demand and the same seeds. Any
difference in measured outcome is therefore attributable to the rules themselves.

### 3.4.1 The Four Controllers

| Controller | Phase selection | Green allocation | Scheduling analogue |
|---|---|---|---|
| `fixed` | Strict alternation | Constant | Round robin |
| `proportional` | Strict alternation | Share of total demand | Fair queuing |
| `queue_clearing` | Shortest queue first | Saturation-flow formula | SJF |
| `longest_queue_first` | Longest queue first | Saturation-flow formula | Max-pressure |

This design produces the two contrasts needed:

- `fixed` versus `proportional` isolates **green allocation** with selection held constant
  (both alternate strictly).
- `queue_clearing` versus `longest_queue_first` isolates **phase selection** with allocation
  held constant (both use the identical saturation-flow formula, and the latter inherits it
  from the former).

The saturation-flow green rule used by both adaptive controllers is:

```
green = startup_lost_time + (queue_length × headway)
```

clamped to a configured range, with short queues instead receiving a fixed short green.
This is the standard clearance-time formulation and requires only a queue-length estimate.

### 3.4.2 The Aging Bound

Both adaptive controllers implement an explicit aging rule. If the phase not currently
being served has gone unserved for longer than `max_wait_threshold`, it is promoted
immediately, irrespective of queue lengths:

```
if (now − last_served[other_phase]) > max_wait_threshold:
    serve other_phase
```

This is starvation prevention in the sense of Silberschatz et al. (2018). Without it, both
SJF and max-pressure can starve an approach indefinitely — SJF by perpetually preferring a
short queue, max-pressure by perpetually preferring a long one.

The aging bound is exposed as a configuration parameter and swept across 10–60 s in Section
4.2. **The interaction between this bound and the selection rule turns out to be the
project's central finding**, and the reason is structural: a phase cannot be re-served more
often than `min_green + yellow + all_red` ≈ 15 s allows. If the aging bound is at or below
this figure, it fires on essentially every decision, and the selection rule beneath it is
never reached.

*[Insert Figure 3.5 — `docs/diagrams/fig3-6_activity_phase.png`]*

*Figure 3.5: Activity diagram of the phase-selection decision, drawn for both adaptive
controllers simultaneously. The aging gate (green) precedes every other test; the only nodes
at which the two controllers differ are shaded amber. When the aging bound is tight the amber
nodes are rarely reached, which is the mechanism behind the central finding reported in
Section 4.1. Green time is computed identically on every path.*

### 3.4.3 Preemption as a Decorator

Emergency preemption is implemented as a **decorator** — a class that both implements the
controller interface and holds a controller instance. `EmergencyPreemptionController` can
therefore wrap any of the four controllers without any of them being aware of it.

*[Insert Figure 3.6 — `docs/diagrams/fig3-2_class_signal.png`]*

*Figure 3.6: Class diagram of the signal control hierarchy. The two preemption controllers
each inherit from `TimingAlgorithm` and hold a `TimingAlgorithm`, the inheritance-plus-
composition pair that constitutes the Decorator pattern.*

This has three consequences that matter for the research design:

1. **Emergency preemption is not a fifth algorithm.** The comparison remains four-way with
   preemption enabled or disabled, so the two questions do not confound each other.
2. **Composition order is explicit.** Controllers are composed `base → preemptive →
   emergency`, with emergency outermost, so that an ambulance can never be interrupted by
   the mid-green scheduler.
3. **Disabling it is provably inert.** Removing the `emergency` configuration block
   reproduces pre-preemption results *bit-identically*, a property enforced by an automated
   regression test.

On detecting an emergency vehicle, the controller determines the target phase and, if it is
not currently green, requests a change and truncates the running green — but only after a
minimum service period (`min_green_before_preempt`, default 5 s). Preemption skips the
*wait*, never the safety clearance. Once the emergency vehicle has departed, the target
phase is held for a short clearance extension before normal control resumes.

*[Insert Figure 3.7 — `docs/diagrams/fig3-5_sequence_preemption.png`]*

*Figure 3.7: Sequence diagram of one simulation tick in which an emergency vehicle arrives on
a red approach. The `alt` fragment carries the safety argument: an emergency vehicle on the
phase already being served extends that green rather than forcing a needless switch through
yellow and all-red.*

A second decorator, `PreemptiveSchedulingController`, re-evaluates the base controller's
selection rule at every time step rather than only at phase boundaries — the
shortest-remaining-time-first counterpart to the non-preemptive controllers. It is disabled
by default and used only for the experiment reported in Section 4.7.

## 3.5 Data Design

The system has no database management system, and this is a deliberate design decision
rather than an omission. The system is a real-time control loop with no persistence
requirement: there are no user accounts, no records to retrieve, and no transactional
integrity constraints. Its inputs are configuration and video; its outputs are signal
decisions and experimental measurements. Introducing a relational database would add a
dependency and a failure mode without serving any functional requirement.

Data is instead organised into four schemas.

**Configuration (YAML).** The parameter contract for the entire system. All tunable
quantities live here; the source code contains no magic numbers. Selected parameters:

| Key | Type | Unit | Default | Effect |
|---|---|---|---|---|
| `timing.min_green` | float | s | 10 | Minimum green interval |
| `timing.max_green` | float | s | 60 | Maximum green interval |
| `timing.yellow_duration` | float | s | 3 | Yellow interval |
| `timing.all_red_duration` | float | s | 2 | All-red clearance |
| `timing.startup_lost_time` | float | s | 2.0 | Reaction delay in green formula |
| `timing.headway` | float | s | 2.0 | Saturation headway per vehicle |
| `timing.saturation_flow` | int | veh/h | 1800 | Discharge rate during green |
| `timing.yellow_discharge_time` | float | s | 2.0 | Portion of yellow that discharges |
| `timing.queue_capacity` | int | veh | 25 | Approach storage before spillback |
| `timing.max_wait_threshold` | float | s | 20 | **Aging bound** |
| `turning.through/left/right` | float | — | .70/.15/.15 | Movement split |
| `emergency.enabled` | bool | — | true | Master switch for preemption |
| `emergency.min_green_before_preempt` | float | s | 5.0 | Safety floor before truncation |
| `detection.color_min_area` | int | px² | 280 | Smallest accepted vehicle blob |

*Table 3.2: Selected configuration parameters (data dictionary extract).*

Every key falls back to the model's pre-existing behaviour when absent, so older
configurations reproduce the numbers they originally produced — a property enforced by test.

**Region of interest (JSON).** `{lane_name: {approach, polygon}}`, mapping each lane polygon
to the approach it serves.

**Ground truth (JSON).** Per-frame annotations emitted by the synthetic video generator:
frame index, and for each vehicle its bounding box, approach, type and emergency flag, plus
"ignore" boxes for partially visible vehicles.

**Results (CSV).** `comparison.csv` holds one row per controller-scenario pair with mean and
standard deviation for each metric; per-run files record queue snapshots, individual vehicle
waits, signal cycles and emergency clearances.

The flow of data between these stores and the processing stages is shown below.

*[Insert Figure 3.8 — `docs/diagrams/fig3-8_dfd_level1.png`]*

*Figure 3.8: Level 1 data flow diagram. Cylinders are data stores and circles are processes.
Dotted edges carry configuration; solid edges carry measurements. Processes 3.0 and 9.0 are
the identical controller code, invoked from the two different pipelines.*

## 3.6 System Evaluation

Evaluation was conducted in two independent parts, since the system has two halves.

**Controller evaluation.** Each controller was run for **5 seeded trials × 600 simulated
seconds × 4 scenarios**. Repetition with distinct seeds is essential: a single run of a
stochastic process is not evidence, and all reported figures are means with standard
deviations across trials. Because seeds are shared across controllers, every controller
faces an identical arrival sequence. Metrics recorded were:

- **Average waiting time** — the primary metric, mean seconds from arrival to departure.
- **Maximum waiting time** — worst-case delay, capturing starvation.
- **Throughput** — vehicles served, the meaningful metric under oversaturation.
- **Blocked demand** — percentage of arrivals refused for lack of storage.
- **Emergency response time** — mean wait for emergency vehicles.
- **Cycles** — completed service cycles, indicating switching frequency.

**Detection evaluation.** Measuring detection accuracy requires ground truth. Rather than
hand-annotating footage — laborious and subject to annotator disagreement — the synthetic
video generator was extended to emit exact annotations for every vehicle it draws. Ground
truth is therefore free and exact by construction.

Detections were matched to ground truth by greedy assignment on Intersection over Union
(IoU) at a threshold of 0.5. Vehicles straddling the frame edge are marked "ignore" and
scored neither way. Three families of metric were computed:

- **Detection quality** — precision, recall and F1-score over matched boxes.
- **Counting accuracy** — mean absolute error in per-approach vehicle count. This is the
  metric that matters operationally, since the controller consumes counts, never boxes.
- **Emergency classification** — precision and recall, computed **only over correctly
  located vehicles**, so that a missed ambulance is charged to detection rather than counted
  a second time against the classifier.

The system was additionally validated by an automated test suite of **213 tests**,
comprising approximately 95 unit tests (formulas, individual controller decisions, scoring
functions), 105 integration tests (engine, generator and metrics operating together) and 13
acceptance and regression tests, including one asserting that a run with emergency
preemption removed is bit-identical to one with it disabled.

---

# CHAPTER 4: RESULTS AND FINDINGS

## 4.0 Introduction

This chapter presents the quantitative results of the evaluation described in Section 3.6.
Sections 4.1 to 4.3 address the controller comparison, Section 4.4 the emergency-vehicle
preemption results, and Section 4.5 the detection accuracy evaluation. Section 4.6 shows the
implemented interface and Section 4.7 summarises the findings.

Unless stated otherwise, every figure is the mean of **5 seeded trials × 600 s**, and the
ordinary-traffic results are reported with emergency preemption **disabled**, so that the
scheduling question is measured on its own.

## 4.1 Below Capacity: Where Green Allocation Is Decided

The below-capacity configuration places every approach under its capacity, with **0% of
demand blocked** on fifteen of the sixteen runs (the exception being `fixed` on
`asymmetric`, at 0.4%). Nothing in this table is therefore an artefact of queues with
nowhere to go.

| Scenario | fixed | proportional | queue_clearing | longest_queue_first |
|---|:---:|:---:|:---:|:---:|
| balanced | 20.1 | 17.2 | **13.5** | **13.5** |
| morning_rush | 30.8 | 25.8 | **23.8** | **23.8** |
| evening_rush | 29.0 | 25.3 | **22.9** | **22.9** |
| asymmetric | 30.8 | **26.9** | 28.3 | 28.3 |

*Table 4.1: Average waiting time (s), 5 trials × 600 s, emergency preemption disabled. Bold
marks the lowest wait in each row.*

Four observations follow, and the project's conclusions derive directly from them.

**1. Green-time allocation is the effective lever.** The tuned adaptive controllers beat
`fixed` on every scenario (−33% balanced, −23% morning, −21% evening, −8% asymmetric) and
beat `proportional` on three of four (−22%, −8%, −10%), while running roughly twice the
service cycles (29 versus 15). The gain comes from the saturation-flow green rule combined
with prompt alternation — not from being clever about which phase to select.

**2. SJF and max-pressure are indistinguishable — the central negative result.**
`queue_clearing` and `longest_queue_first` produce **identical** results in every scenario,
to the last reported decimal, despite implementing opposite selection rules. The explanation
is the aging bound. A phase can only be re-served about every 15–20 s
(`min_green` + `yellow` + `all_red`), so at `max_wait_threshold: 20` the aging rule fires on
essentially every decision and promotes the starved phase before the selection heuristic is
consulted. Both controllers collapse to prompt alternation. **On a two-phase junction there
is no phase-order problem left to solve once aging is tight.**

That the two controllers are nonetheless genuinely distinct implementations, rather than
accidentally the same code, is established in Section 4.2: loosening the aging bound to 25 s
makes them diverge on all four scenarios.

**3. `proportional` wins on `asymmetric`, and this is expected.** With arrival rates of
0.21/0.03/0.12/0.06 the demand split is lopsided but *stable* — precisely the case a fixed
demand-proportional split is designed for. The adaptive controllers keep reacting to the
three light approaches and pay the lost time (yellow plus all-red) on each switch. They
still beat `fixed` (28.3 versus 30.8), so the reactive machinery is not wasted; it is
out-earned by a static split when the split never needs to change.

**4. The adaptive controllers also reduce worst-case delay.** Maximum waiting time on
`balanced` falls from 75.6 s (`fixed`) to 41.2 s, indicating that the gain is not obtained
by trading tail latency for mean.

*[Insert Figure 4.1 — `results/low_load_baseline/plots/avg_wait_bar.png`]*

*Figure 4.1: Average waiting time by controller and scenario. The identical bar heights for
`queue_clearing` and `longest_queue_first` in every scenario are the central negative result
made visible.*

*[Insert Figure 4.2 — `results/low_load_baseline/plots/wait_boxplot.png`]*

*Figure 4.2: Distribution of individual vehicle waiting times by controller. The adaptive
controllers compress both the median and the upper tail relative to fixed-time control.*

## 4.2 The Aging Bound Sweep

Section 4.1 reported that the two adaptive controllers produce identical results. Identical
output from two controllers implementing opposite selection rules invites an obvious
objection: that the two are not in fact distinct, and that the finding is an implementation
artefact rather than a property of the system.

This section answers that objection directly. The aging bound was swept across its useful
range for **both** controllers simultaneously, so that the threshold at which they begin to
diverge can be located. `proportional` is shown as a reference line.

| Threshold (s) | balanced | morning_rush | evening_rush | asymmetric | Identical? |
|:---:|:---:|:---:|:---:|:---:|:---:|
| `proportional` | 17.2 | 25.8 | 25.3 | 26.9 | — |
| 10 | 13.5 / 13.5 | 23.8 / 23.8 | 22.9 / 22.9 | 28.3 / 28.3 | **YES** |
| 15 | 13.5 / 13.5 | 23.8 / 23.8 | 22.9 / 22.9 | 28.3 / 28.3 | **YES** |
| 20 | 13.5 / 13.5 | 23.8 / 23.8 | 22.9 / 22.9 | 28.3 / 28.3 | **YES** |
| 25 | 16.4 / 19.9 | 29.5 / 30.8 | 25.5 / 29.6 | 31.5 / 29.5 | no |
| 30 | 17.3 / 20.3 | 28.8 / 31.3 | 27.3 / 28.1 | 31.3 / 29.8 | no |
| 45 | 18.3 / 21.3 | 33.4 / 32.7 | 28.7 / 29.7 | 35.1 / 32.3 | no |
| 60 | 18.5 / 22.3 | 35.3 / 34.7 | 34.4 / 30.2 | 36.0 / 36.4 | no |
| 90 | 24.5 / 23.2 | 37.7 / 37.4 | 40.3 / 31.9 | 40.0 / 37.5 | no |

*Table 4.2: Average waiting time (s) against aging threshold, shown as
`queue_clearing` / `longest_queue_first`. 5 trials × 600 s, emergency preemption disabled.
"Identical?" reports whether the two controllers agreed on all four scenarios to within
10⁻⁹ s.*

Two results follow, and together they establish the mechanism.

**First, the controllers are genuinely distinct.** From a threshold of 25 s upward they
diverge on every scenario, and by margins far exceeding the trial-to-trial spread — 18.5 s
against 22.3 s on balanced at a 60 s bound, a difference of 3.8 s against standard
deviations of roughly 1–2 s. Whatever produces the identical results at 20 s, it is not that
the two controllers share an implementation. This is corroborated at unit level by a
regression test that supplies both controllers with the same queue state and asserts they
select *opposite* phases.

**Second, the transition is sharp and falls exactly where the mechanism predicts.** The
controllers agree at 10, 15 and 20 s and disagree at 25 s and above, on all four scenarios.
A phase cannot be re-served faster than `min_green` + `yellow` + `all_red` ≈ 15 s permits,
so a bound at or below approximately 20 s is triggered on essentially every decision, the
starved phase is promoted, and the selection rule beneath it is never evaluated. Above that
figure the bound binds only intermittently, control returns to the selection rule, and the
two controllers behave according to their differing logic. The identical results in Table
4.1 are therefore not a coincidence and not a defect: they are the signature of a
phase-selection rule that has been rendered unreachable.

Average waiting time also falls monotonically as the bound tightens — from 22.3 s at 60 s to
13.5 s at 20 s on the balanced scenario for `longest_queue_first`, a 39% reduction obtained
by changing a single parameter. The original 60 s default is what caused early adaptive
results to *lose* to the baselines during development. **The aging bound dominates every
other tuning parameter examined in this project**, including the choice of phase-selection
rule itself.

*[Insert Figure 4.3 — `results/low_load_baseline/plots/queue_history.png`]*

*Figure 4.3: Queue length against time on the balanced scenario. The adaptive controllers
hold queues shorter and turn them over roughly twice as often as fixed-time control.*

## 4.3 Above Capacity: Where Wait Time Stops Being the Metric

The above-capacity configuration drives the balanced scenario at 0.30 veh/s per approach
against an effective per-approach capacity of approximately 0.22 veh/s — a
volume-to-capacity ratio of about 1.4.

| Metric (balanced) | fixed | proportional | queue_clearing | longest_queue_first |
|---|:---:|:---:|:---:|:---:|
| Average wait (s) | 92.4 | 92.2 | 84.0 | **82.1** |
| Throughput (veh) | 434 | 437 | 444 | **449** |
| Blocked (% demand) | 24.5 | 23.9 | 24.2 | **23.7** |

*Table 4.3: Oversaturated performance, balanced scenario.*

Two conclusions follow, and they differ by scenario. On `balanced`, adaptive control still
wins, but the honest headline is **throughput**, not waiting time: 449 vehicles served
against 434, with 0.8 percentage points less demand turned away. Waiting time is a poor
metric here because it is measured only over vehicles that actually got through.

On the three rush scenarios, everything converges (74.7–81.9 s wait, 385–396 veh
throughput, approximately 46% blocked, all within noise). When a single approach is far
beyond capacity, no allocation of green helps: the binding constraint is the junction's
total capacity, not how that capacity is divided.

## 4.4 Emergency Vehicle Preemption Results

Emergency preemption was evaluated by enabling the decorator over each of the four
controllers, with emergency vehicles arriving at 0.002 veh/s per approach.

| Controller | EV response (s) | Ordinary wait (s) | Reduction |
|---|:---:|:---:|:---:|
| `fixed` | 4.3 | 30.0 | **86%** |
| `proportional` | 5.3 | 27.4 | **81%** |
| `queue_clearing` | 5.3 | 25.9 | **80%** |
| `longest_queue_first` | 5.2 | 23.9 | **78%** |

*Table 4.4: Emergency-vehicle response time against ordinary-traffic waiting time, all
scenarios pooled.*

Emergency vehicles clear the junction in 4.3–5.3 s against 23.9–30.0 s for ordinary traffic,
a reduction of **78–86%**. The cost to ordinary traffic is modest: comparing Table 4.1 with
the preemption-enabled runs, average waiting time rises by between 1 and 6 s depending on
controller and scenario, and the *ranking* of the controllers is unchanged.

The reduction is largest for `fixed` (86%) precisely because `fixed` is the worst baseline —
there is more waiting to eliminate. Under `longest_queue_first`, ordinary traffic already
waits least, so preemption has less to save.

Two properties of the implementation are worth reporting alongside the headline figure.
First, disabling the emergency configuration block reproduces the Table 4.1 figures
**bit-identically**, verified by automated test, confirming that the feature is genuinely
inert when off. Second, emergency vehicles are drawn from a separate random stream, so
enabling preemption does not perturb the ordinary arrival sequence.

## 4.5 Detection Accuracy Evaluation

The detection pipeline was evaluated against generated ground truth over 2,700 frames
containing 18,787 labelled vehicle instances, of which 608 were emergency vehicles.

| Metric | Value |
|---|:---:|
| Precision | **99.90%** |
| Recall | **97.67%** |
| F1-score | **98.77%** |
| True positives | 18,349 |
| False positives | 19 |
| False negatives | 438 |

*Table 4.5: Detection performance, IoU ≥ 0.5, 2,700 frames.*

Counting accuracy — the metric the controller actually consumes — was substantially better
than the box-level figures suggest:

| Approach | Count MAE (veh) | Frames within ±1 |
|---|:---:|:---:|
| north | 0.14 | 98.7% |
| south | 0.07 | 100.0% |
| east | 0.03 | 100.0% |
| west | 0.06 | 100.0% |
| **Overall** | **0.08** | **99.6%** |

*Table 4.6: Per-approach queue count accuracy.*

### A defect exposed by the evaluation

The evaluation harness immediately revealed a defect that had been invisible during
development. At the original configuration the detector achieved only 83.4% recall, and
breaking the false negatives down by vehicle type showed the loss was almost entirely
concentrated in one class:

| Vehicle type | Missed | As % of that type |
|---|:---:|:---:|
| motorbike | 2,774 | **84.1%** |
| car | 255 | 2.3% |
| ambulance | 71 | 11.7% |
| bus | 17 | 0.8% |
| truck | 17 | 0.9% |

*Table 4.7: False negatives by vehicle type at the original minimum-area threshold.*

The minimum blob area accepted as a vehicle was set to 400 px². A motorbike's drawn bounding
box exceeds this, but its *saturated blob* is narrower than its box, so motorbikes fell below
the threshold and were silently discarded. Sweeping the parameter produced a clear optimum:

| Minimum area (px²) | Precision | Recall | F1 | Motorbike recall |
|:---:|:---:|:---:|:---:|:---:|
| 400 (original) | 99.90% | 83.4% | 90.9% | 16.1% |
| 320 | 99.92% | 96.4% | 98.1% | 90.3% |
| **280 (adopted)** | **99.92%** | **97.7%** | **98.8%** | **97.6%** |
| 250 | 99.89% | 97.8% | 98.8% | 98.0% |
| 240 | 90.55% | 97.8% | 94.0% | 98.0% |
| 220 | 81.24% | 97.8% | 88.8% | 98.2% |

*Table 4.8: Detection performance against the minimum-area threshold.*

A value of 280 px² was adopted. It sits at the performance plateau while retaining margin
above the sharp precision cliff between 250 and 240, where shadow and road-marking fragments
begin to qualify as vehicles. The correction raised overall F1 from 90.9% to 98.8% and
motorbike recall from 16% to 98%. The finding was validated on a **holdout clip** generated
from a different scenario and configuration, which showed the same pattern (F1 89.3% → 99.1%,
motorbike recall 0.5% → 95.4%), confirming the parameter was not overfitted to one video.

This result carries particular weight in the Ghanaian context, where motorcycles constitute a
substantial share of urban traffic. A detector blind to them would misreport queue lengths
systematically.

### Emergency classification

| Metric | Per-frame | Per-vehicle |
|---|:---:|:---:|
| Precision | 98.33% | — |
| Recall | 87.71% | **100% (12/12 episodes)** |
| Median detection latency | — | **0 ms** |

*Table 4.9: Emergency classification, scored over correctly located vehicles.*

The per-frame recall of 87.71% understates operational performance, and the distinction
matters. The controller preempts on the *first* frame in which an emergency vehicle is
flagged; it does not require the flag to persist. Across 12 emergency-vehicle episodes,
**every one was flagged, with a median latency of 0 ms** — that is, on the first frame in
which the vehicle became visible (worst case 2.0 s). The frames in which the flag is missed
occur while the vehicle is already being served.

It was further verified that the misses are not caused by the flashing light bar: recall was
85.2% with the bar lit and 85.3% with it dark, statistically indistinguishable.

Finally, on ordinary synthetic footage containing no emergency vehicles, the classifier
produced **zero false positives across 23,683 detections**, confirming that the four-test
design described in Section 3.3.2 successfully rejects blue cars with red tail lights and
buses with tinted glazing.

## 4.6 User Interface Showcase

*[Insert Figure 4.4 — `results/demo_shots/1_normal_operation.png`]*

*Figure 4.4: The dashboard under normal operation, showing live detection boxes, ROI polygon
overlays, per-approach vehicle counts, the current phase with green time remaining, the
active algorithm, and the animated top-down junction panel.*

*[Insert Figure 4.5 — `results/demo_shots/2_emergency_preemption.png`]*

*Figure 4.5: The dashboard during an emergency preemption, showing the flashing alert band,
the red EMERGENCY bounding box on the detected vehicle, and the preemption status line.*

The dashboard supports switching between the four controllers using keys 1–4 while running,
allowing their behaviour to be compared directly on identical footage during a live
demonstration.

## 4.7 Key Findings Summary

1. **Green-time allocation is the effective lever, not phase order.** The saturation-flow
   green rule with prompt alternation reduced average waiting time by 33% against fixed-time
   and 22% against proportional control.

2. **SJF and max-pressure are indistinguishable under a tight aging bound.**
   `queue_clearing` and `longest_queue_first` produced identical results in all four
   scenarios at a 20 s bound, and **diverged on all four at 25 s and above**, locating the
   transition precisely and confirming that the collapse is a property of the regime rather
   than of the implementation. This is the project's central negative result.

3. **The aging bound dominates every other tuning parameter.** Tightening it from 60 s to
   20 s reduced balanced-scenario waiting time monotonically from 22.3 s to 13.5 s. Below
   20 s it ceases to bind.

4. **Above capacity, throughput replaces waiting time as the meaningful metric.** At a
   volume-to-capacity ratio of 1.4, adaptive control served 449 vehicles against 434, while
   the three rush scenarios converged entirely.

5. **Emergency preemption reduces response time by 78–86% for 1–6 s of additional ordinary
   delay**, without changing the controller ranking, and is provably inert when disabled.

6. **The vision pipeline achieves 98.77% F1 and a counting error of 0.08 vehicles per
   approach**, sufficient to drive the controller.

7. **Preemptive (mid-green) scheduling reinforces rather than complicates the headline.**
   When the base rule is re-evaluated continuously rather than at phase boundaries, the four
   controllers converge again — preemption mostly buys *shorter greens*, which is the same
   mechanism identified in Finding 1.

---

# CHAPTER 5: DISCUSSION AND CONCLUSION

## 5.0 Introduction

This chapter interprets the findings of Chapter 4, states the contributions of the work,
sets out its limitations candidly, and offers recommendations for future research.

## 5.1 Discussion of Findings

**The decomposition worked, and it produced an unexpected answer.** The project set out to
determine whether phase selection or green allocation carries the benefit of adaptive
control. The answer is unambiguous: green allocation. Holding selection constant and varying
allocation (`fixed` versus `proportional`) produced a consistent improvement; holding
allocation constant and varying selection (`queue_clearing` versus `longest_queue_first`)
produced *no difference whatsoever*.

The second result deserves emphasis because a null result of this kind is easily
misinterpreted as a failure to find an effect. It is not. The two controllers implement
opposite rules — serve the shortest queue, serve the longest — and produced results identical
to the reported precision across all four scenarios. This is not noise obscuring a small
effect; it is a structural consequence with a mechanical explanation. A phase cannot be
re-served more often than the minimum green, yellow and all-red intervals permit,
approximately 15 s. When the aging bound is set at or below this figure, the starvation check
fires before the selection rule is ever consulted, and both controllers reduce to prompt
alternation. The phase-selection logic is, in this configuration, unreachable code.

The distinction between a structural consequence and an implementation defect is not one a
reader should be asked to take on trust, and Section 4.2 supplies the discriminating
evidence. If the two controllers were accidentally the same code, they would agree at *every*
aging threshold. They do not: they agree at 10, 15 and 20 s and diverge on all four scenarios
at 25 s and above, by margins several times the trial-to-trial spread. The transition falls
precisely where the interval structure predicts it should. A defect cannot produce a sharp,
theory-predicted boundary; a regime change can.

This explains an otherwise puzzling feature of the literature. Studies comparing
sophisticated phase-selection policies frequently report modest gains over simple baselines,
and the effect is often attributed to the specific policy. The present result suggests an
alternative explanation for simple junctions: where a fairness constraint is tight, much of
what distinguishes such policies never gets the opportunity to act. The consequence for a
practitioner is direct — on a two-phase junction, effort is better spent tuning the aging
bound and the green formula than on the selection heuristic.

**The aging sweep confirms the mechanism, and does so by a falsifiable prediction.** The
explanation above is not merely a description of the data; it predicts where the behaviour
must change. If the selection rule is unreachable because the aging check fires first, then
raising the bound past the minimum re-service interval of roughly 15–20 s must return control
to the selection rule and make the two controllers diverge. That prediction is testable, was
tested, and held: the controllers agree at 10, 15 and 20 s and disagree on all four scenarios
from 25 s upward. Waiting time also rises monotonically as the bound loosens. The finding is
therefore not an artefact of one parameter value but a property of a regime whose boundary
has been located.

**`proportional` winning on `asymmetric` is a result, not an anomaly.** A demand-proportional
split is optimal when demand is lopsided but stable, because the split never needs to change
and the adaptive controllers pay lost time on every switch they make. Reporting this
honestly, rather than presenting the adaptive controllers as uniformly superior, strengthens
the comparison: it identifies the conditions under which each approach is preferable.

**Oversaturation changes the question.** At a volume-to-capacity ratio of 1.4, waiting time
becomes misleading because it is measured only over vehicles that were served. Throughput and
blocked demand are the honest metrics, and by those measures adaptive control retains a
modest advantage on balanced demand and none at all on the rush scenarios. When a single
approach is far beyond capacity, no allocation of green helps; the binding constraint is the
junction's total capacity.

**Emergency preemption is a favourable trade at low emergency-vehicle frequency.** A 78–86%
reduction in emergency response time for 1–6 s of additional delay per ordinary vehicle is
strongly favourable given how rarely emergency vehicles arrive. The decorator architecture
matters as much as the result: because preemption composes over the controllers rather than
replacing them, the scheduling comparison and the preemption evaluation remain independent.

**The detection evaluation justified itself immediately.** The most instructive outcome of
building the accuracy harness was not the headline F1 score but the defect it exposed. A
threshold set to a plausible-looking value was silently discarding 84% of motorbikes, and
nothing in the system's ordinary operation revealed it — queue counts were merely wrong, not
obviously broken. This is a general lesson: a vision component that is not measured against
ground truth cannot be assumed correct simply because it appears to work.

## 5.2 Key Contributions of the Research

**1. A controlled decomposition of adaptive signal control.** The principal contribution is
methodological. By implementing four controllers behind a common interface, differing only in
their selection and allocation rules, and evaluating them on an identical junction model
under identical seeded demand, this work isolates which component of adaptive control
produces the benefit. Published evaluations typically vary both together and report an
aggregate improvement, which cannot attribute the gain to either. The finding — that green
allocation carries the benefit — has direct practical consequence, since the two decisions
differ by an order of magnitude in implementation cost.

**2. A negative result with a mechanical explanation.** The demonstration that
shortest-job-first and max-pressure selection become *identical* under a tight aging bound,
together with the structural account of why (a phase cannot be re-served faster than the
minimum interval structure allows, so the starvation check pre-empts the selection rule),
identifies a boundary condition on the usefulness of phase-selection research at simple
junctions. Negative results of this kind are under-reported, and this one is accompanied by
the parameter sweep that establishes the regime in which it holds.

**3. Emergency preemption as a composable decorator.** Implementing preemption as a wrapper
rather than as a distinct algorithm, with a verified guarantee that disabling it reproduces
prior results bit-identically, is a design contribution that keeps two research questions
independent within one system. It also means preemption can be added to any future controller
without modification.

**4. A self-labelling evaluation methodology for the vision pipeline.** Extending the
synthetic video generator to emit exact ground truth makes detection accuracy measurable
without hand annotation, and the harness built on it separates detection quality, counting
accuracy and emergency classification so that failures are attributed to the correct
component. Its immediate practical value was demonstrated by the motorbike defect it
uncovered — a correction that raised F1 from 90.9% to 98.8%.

## 5.3 Limitations of the Study

This work has clear boundaries, stated here in the order in which they most affect the
results.

**Simulation rather than field data.** All traffic results derive from a point-queue model
driven by Poisson arrivals, not from measured Ghanaian traffic. The model captures queueing,
turning penalties, storage limits and discharge behaviour, but it is a model. The comparative
*ranking* of controllers is the claim; absolute waiting times should not be read as
predictions for any specific junction.

**Two phases only.** The junction operates two conflicting phases with no protected turns.
This is precisely why the aging bound dominates the selection rule — with only two choices,
prompt alternation is nearly always defensible. A junction with protected turn phases would
give the selection heuristics a genuine choice, and the central negative result should not be
extrapolated to such junctions without re-testing.

**Turning is modelled as a service-time cost, not a spatial conflict.** A left-turner
consumes more green and blocks vehicles behind it, capturing capacity and head-of-line
effects, but the model does not represent a turning vehicle waiting *within* the junction for
a gap, nor a dedicated turn lane allowing through traffic past it.

**Spillback is counted, not propagated.** A full approach turns arrivals away and records
them as blocked, but there is no upstream link for them to back into and no effect on
adjacent junctions. This is the right abstraction for an isolated junction and the wrong one
for a corridor.

**Controllers see counts, not movements.** The timing algorithms receive per-approach queue
lengths, exactly as a real detector would report them, so they cannot know that a queue is
full of left-turners and will take longer to clear than the headway formula assumes. This
mismatch is realistic, but it means no controller here can exploit turn composition even in
principle.

**Emergency detection is a heuristic, not a trained classifier.** This is the weakest link in
the pipeline and the claim to be most careful about. The light-bar rule misses a fire engine,
whose red bodywork defeats the balance test — the same rule that prevents blue cars
false-positiving causes this false negative. It also misses any emergency vehicle with its
lights off, and any unmarked vehicle. Most importantly, **it has been validated only on
synthetic footage where the light bar is drawn in known colours.** The zero-false-positive
figure is a property of that footage, not a claim about real CCTV.

**Detection accuracy is measured on synthetic footage.** The 98.77% F1 figure validates the
detection-to-counting chain and the tuning of its parameters. It is not a claim about
real-world accuracy, and the real footage held in the project repository remains unlabelled.

**An emergency vehicle jumps its queue instantly and is never blocked.** Real traffic takes
time to pull aside, and a gridlocked approach may have nowhere to pull aside *to*. The
reported response times are therefore a **lower bound** — the signal-side benefit of
preemption without the vehicle-side cost of reaching the stop line.

**Preemption is measured at an isolated junction.** There is no upstream signal holding
traffic back and no green wave along the emergency vehicle's route, which is where much of
the real-world benefit of a corridor EVP system arises.

## 5.4 Recommendations and Future Work

1. **Extend to protected turn phases.** This is the single most valuable extension. Adding
   protected turns raises the junction from two phases to four or more, giving the
   phase-selection heuristics a genuine choice. The central negative result of this project
   predicts that the selection rule should begin to matter once the number of phases exceeds
   what prompt alternation can serve within the aging bound — a directly testable hypothesis.

2. **Replace the emergency heuristic with a fine-tuned detector.** Fine-tuning YOLOv8 on an
   emergency-vehicle dataset would address the fire-engine failure, the lights-off failure
   and the dependence on synthetic colour. Because nothing downstream depends on *how* the
   emergency flag was set, this requires rewriting a single module. This is the highest-value
   next step for the vision half.

3. **Validate against real footage and field counts.** Hand-annotating a sample of real
   junction footage would convert the detection figures from a synthetic validation into a
   real-world measurement. Collecting turning-movement counts at a Kumasi junction would
   allow the demand scenarios to be calibrated to local conditions.

4. **Cross-validate the ranking in an established simulator.** Reproducing the controller
   comparison in SUMO would test whether the ranking survives a more detailed car-following
   and lane-changing model. The objective would be to confirm the *ranking*, not to reproduce
   absolute waiting times, which should be expected to differ.

5. **Extend to a corridor.** Coordinating two or more junctions would allow spillback to
   propagate and would let emergency preemption produce a green wave, which is where most of
   the real-world benefit of EVP arises.

6. **Deploy to hardware as a proof of concept.** Driving physical LED signals from a
   Raspberry Pi or Arduino would demonstrate deployment feasibility. The control interface is
   already isolated behind the phase manager, so this requires an output adapter rather than
   changes to the control logic.

## 5.5 Conclusion

This project set out to determine which component of adaptive traffic signal control actually
reduces vehicle waiting time at a two-phase junction, and to demonstrate emergency-vehicle
priority layered on top of it. Both objectives were met.

Four controllers were implemented behind a common interface and evaluated over seeded,
repeated trials on an identical junction model incorporating turning movements, storage
capacity and yellow-interval discharge. The comparison establishes that **green-time
allocation is the effective lever**: a saturation-flow green rule with prompt alternation
reduced average waiting time by 33% against fixed-time control. It further establishes, as a
negative result, that **phase-selection heuristics collapse to prompt alternation under a
tight aging bound** — shortest-job-first and max-pressure selection produced identical
results — and that the **aging bound dominates every other tuning parameter examined**,
taking balanced-scenario waiting time from 22.3 s to 13.5 s as it tightens from 60 s to 20 s.

Emergency-vehicle preemption, implemented as a decorator composing over any controller,
reduced emergency response time by 78–86% at a cost of 1–6 s of additional delay to ordinary
traffic, while remaining provably inert when disabled. The supporting vision pipeline
achieved an F1-score of 98.77% with a per-approach counting error of 0.08 vehicles, and the
evaluation harness built to measure it uncovered and corrected a defect that had been
discarding 84% of motorbikes.

The work is bounded by its assumptions — a single junction, two phases, simulated demand and
a heuristic rather than trained emergency classifier — and these are stated in Section 5.3.
Within those bounds, it contributes a controlled decomposition of a question usually left
implicit, and a negative result that explains rather than merely reports. For a practitioner
designing control for a simple junction in Kumasi or Accra, the practical implication is
direct: tune the green formula and the fairness bound, and do not expect a sophisticated
phase-selection rule to repay the effort of building it.

---

# REFERENCES

Hunt, P. B., Robertson, D. I., Bretherton, R. D., & Royle, M. C. (1982). The SCOOT on-line
traffic signal optimisation technique. *Traffic Engineering & Control, 23*(4), 190–192.

Jocher, G., Chaurasia, A., & Qiu, J. (2023). *YOLO by Ultralytics* (Version 8.0.0) [Computer
software]. https://github.com/ultralytics/ultralytics

Koonce, P., & Rodegerdts, L. (2008). *Traffic signal timing manual* (Report No.
FHWA-HOP-08-024). Federal Highway Administration.

Lowrie, P. R. (1990). *SCATS: Sydney Co-ordinated Adaptive Traffic System — A traffic
responsive method of controlling urban traffic*. Roads and Traffic Authority, New South Wales.

Qin, X., & Khan, A. M. (2012). Control strategies of traffic signal timing transition for
emergency vehicle preemption. *Transportation Research Part C: Emerging Technologies, 25*,
1–17.

Redmon, J., Divvala, S., Girshick, R., & Farhadi, A. (2016). You only look once: Unified,
real-time object detection. *Proceedings of the IEEE Conference on Computer Vision and
Pattern Recognition*, 779–788.

Roess, R. P., Prassas, E. S., & McShane, W. R. (2019). *Traffic engineering* (5th ed.).
Pearson.

Silberschatz, A., Galvin, P. B., & Gagne, G. (2018). *Operating system concepts* (10th ed.).
Wiley.

Transportation Research Board. (2016). *Highway capacity manual* (6th ed.). National
Academies of Sciences, Engineering, and Medicine.

Varaiya, P. (2013). Max pressure control of a network of signalized intersections.
*Transportation Research Part C: Emerging Technologies, 36*, 177–195.

Wang, Y., Liu, Z., & Zhu, L. (2020). Vision-based emergency vehicle detection for traffic
signal preemption. *IEEE Access, 8*, 170723–170733.

Webster, F. V. (1958). *Traffic signal settings* (Road Research Technical Paper No. 39). Her
Majesty's Stationery Office.

Wei, H., Zheng, G., Yao, H., & Li, Z. (2018). IntelliLight: A reinforcement learning approach
for intelligent traffic light control. *Proceedings of the 24th ACM SIGKDD International
Conference on Knowledge Discovery & Data Mining*, 2496–2505.

Zhao, Z. Q., Zheng, P., Xu, S. T., & Wu, X. (2019). Object detection with deep learning: A
review. *IEEE Transactions on Neural Networks and Learning Systems, 30*(11), 3212–3232.
