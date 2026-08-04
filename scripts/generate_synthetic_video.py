#!/usr/bin/env python3
"""
Synthetic top-down traffic video generator.

Vehicles drive in from the edge of the frame, queue behind the stop line,
slide forward when the car ahead departs, then move through the intersection
and off-screen on green.

Outputs:
  data/videos/synthetic.mp4
  config/synthetic_roi.json
"""
import sys, os, json, argparse, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
import yaml

# ── Geometry ─────────────────────────────────────────────────────────────────
W, H, FPS = 1280, 720, 30
DT        = 1.0 / FPS
CX, CY    = W // 2, H // 2
HALF_R    = 60          # one lane width / half road width

LANE_CX = {"north": CX - HALF_R // 2, "south": CX + HALF_R // 2}  # 610, 670
LANE_CY = {"east":  CY - HALF_R // 2, "west":  CY + HALF_R // 2}  # 330, 390

SL = {                          # stop-line coordinates
    "north": CY - HALF_R,       # y=300
    "south": CY + HALF_R,       # y=420
    "east":  CX + HALF_R,       # x=700
    "west":  CX - HALF_R,       # x=580
}

VW = {"north": 26, "south": 26, "east": 46, "west": 46}  # vehicle pixel width
VH = {"north": 46, "south": 46, "east": 26, "west": 26}  # vehicle pixel height
VGAP = 8   # gap between queued vehicles

V_ENTER  = 3.5  # px/frame — entering from edge
V_DEPART = 5.0  # px/frame — clearing the intersection
V_SLIDE  = 4.0  # px/frame — sliding forward in queue

MAX_SLOTS = 11  # queue slots shown on-screen per approach

# Colors (BGR)
VEH_CLR = {
    "north": (55,  145, 215),   # orange
    "south": (55,  195,  55),   # green
    "east":  (195,  55,  55),   # blue
    "west":  (195, 195,  45),   # cyan/yellow
}
SIG_CLR = {"green": (0,210,0), "yellow": (0,210,210), "red": (20,20,195)}

# Emergency vehicle livery (BGR). The body is a saturated fluorescent lime so
# the saturation-threshold detector picks the whole vehicle up as ONE blob —
# a white ambulance body would fall below the saturation floor and only the
# light bar would be found. The red and blue bars on top are what
# EmergencyClassifier keys on.
EV_BODY = ( 40, 235, 190)   # fluorescent lime-yellow
EV_RED  = ( 40,  40, 240)
EV_BLUE = (240,  70,  40)

APPROACH_PHASE = {"north":"NS","south":"NS","east":"EW","west":"EW"}
APPROACHES     = ["north","south","east","west"]


# ── Vehicle class ─────────────────────────────────────────────────────────────

class Vehicle:
    """Single animated vehicle with entering / queued / sliding / departing states."""

    def __init__(self, approach: str, slot: int, is_emergency: bool = False):
        self.approach     = approach
        self.slot         = slot
        self.state        = "entering"
        self.is_emergency = is_emergency

        # Start at edge of frame
        if   approach == "north": self.x, self.y = float(LANE_CX["north"]), float(-VH["north"])
        elif approach == "south": self.x, self.y = float(LANE_CX["south"]), float(H + VH["south"])
        elif approach == "east":  self.x, self.y = float(W + VW["east"]),   float(LANE_CY["east"])
        else:                     self.x, self.y = float(-VW["west"]),       float(LANE_CY["west"])

        tx, ty = slot_pos(approach, slot)
        self.tx, self.ty = float(tx), float(ty)

    def _move_toward(self, speed: float):
        dx, dy = self.tx - self.x, self.ty - self.y
        dist   = math.hypot(dx, dy)
        if dist <= speed:
            self.x, self.y = self.tx, self.ty
            self.state = "queued"
        else:
            self.x += dx / dist * speed
            self.y += dy / dist * speed

    def update(self):
        if   self.state == "entering":  self._move_toward(V_ENTER)
        elif self.state == "sliding":   self._move_toward(V_SLIDE)
        elif self.state == "departing":
            if   self.approach == "north": self.y += V_DEPART
            elif self.approach == "south": self.y -= V_DEPART
            elif self.approach == "east":  self.x -= V_DEPART
            else:                          self.x += V_DEPART

    def is_offscreen(self) -> bool:
        m = 90
        if self.approach == "north": return self.y > CY + HALF_R + m
        if self.approach == "south": return self.y < CY - HALF_R - m
        if self.approach == "east":  return self.x < CX - HALF_R - m
        return                              self.x > CX + HALF_R + m

    def set_slot(self, new_slot: int):
        """Reassign queue slot — triggers sliding animation."""
        self.slot = new_slot
        tx, ty = slot_pos(self.approach, new_slot)
        self.tx, self.ty = float(tx), float(ty)
        if self.state == "queued":
            self.state = "sliding"

    def depart(self):
        """Front vehicle leaves — set straight-through departure."""
        self.state = "departing"
        # Snap to stop-line centre so the exit path is clean
        if   self.approach == "north": self.x, self.y = float(LANE_CX["north"]), float(SL["north"])
        elif self.approach == "south": self.x, self.y = float(LANE_CX["south"]), float(SL["south"])
        elif self.approach == "east":  self.x, self.y = float(SL["east"]),        float(LANE_CY["east"])
        else:                          self.x, self.y = float(SL["west"]),         float(LANE_CY["west"])


# ── Geometry helpers ──────────────────────────────────────────────────────────

def slot_pos(approach: str, slot: int):
    vw, vh = VW[approach], VH[approach]
    step   = (vh + VGAP) if approach in ("north","south") else (vw + VGAP)
    if approach == "north": return LANE_CX["north"], SL["north"] - vh//2 - slot*step
    if approach == "south": return LANE_CX["south"], SL["south"] + vh//2 + slot*step
    if approach == "east":  return SL["east"]  + vw//2 + slot*step, LANE_CY["east"]
    return                         SL["west"]  - vw//2 - slot*step, LANE_CY["west"]


# ── Drawing ───────────────────────────────────────────────────────────────────

def draw_road(canvas):
    canvas[:] = (26, 26, 26)
    rd = (60, 60, 60)
    cv2.rectangle(canvas, (0, CY-HALF_R),         (W, CY+HALF_R),         rd, -1)
    cv2.rectangle(canvas, (CX-HALF_R, 0),          (CX+HALF_R, H),          rd, -1)
    cv2.rectangle(canvas, (CX-HALF_R, CY-HALF_R),  (CX+HALF_R, CY+HALF_R), (70,70,70), -1)

    # Dashed centre-lines
    mk = (135, 135, 135)
    for y in list(range(0, CY-HALF_R, 24)) + list(range(CY+HALF_R, H, 24)):
        cv2.line(canvas, (CX, y), (CX, y+14), mk, 2)
    for x in list(range(0, CX-HALF_R, 24)) + list(range(CX+HALF_R, W, 24)):
        cv2.line(canvas, (x, CY), (x+14, CY), mk, 2)

    # Zebra crossings
    zb = (185, 185, 185)
    for i in range(5):
        s = i * 16
        cv2.rectangle(canvas, (CX-HALF_R+s,    SL["north"]-12), (CX-HALF_R+s+8, SL["north"]),   zb, -1)
        cv2.rectangle(canvas, (CX+s,            SL["south"]),    (CX+s+8,        SL["south"]+12),zb, -1)
        cv2.rectangle(canvas, (SL["east"],       CY-HALF_R+s),   (SL["east"]+12, CY-HALF_R+s+8), zb, -1)
        cv2.rectangle(canvas, (SL["west"]-12,    CY+s),          (SL["west"],    CY+s+8),         zb, -1)

    # Stop lines
    wh = (235, 235, 235)
    cv2.line(canvas, (CX-HALF_R, SL["north"]), (CX,         SL["north"]), wh, 3)
    cv2.line(canvas, (CX,        SL["south"]), (CX+HALF_R,  SL["south"]), wh, 3)
    cv2.line(canvas, (SL["east"],CY-HALF_R),   (SL["east"], CY),          wh, 3)
    cv2.line(canvas, (SL["west"],CY),          (SL["west"], CY+HALF_R),   wh, 3)

    # Direction arrows on roads
    ac = (95, 95, 95)
    cv2.arrowedLine(canvas, (LANE_CX["north"], 90), (LANE_CX["north"],118), ac, 2, tipLength=0.4)
    cv2.arrowedLine(canvas, (LANE_CX["south"], H-90),(LANE_CX["south"],H-118),ac,2,tipLength=0.4)
    cv2.arrowedLine(canvas, (W-90, LANE_CY["east"]), (W-118, LANE_CY["east"]),  ac, 2, tipLength=0.4)
    cv2.arrowedLine(canvas, (90,   LANE_CY["west"]), (118,   LANE_CY["west"]),  ac, 2, tipLength=0.4)


def draw_signals(canvas, signal_colors: dict):
    positions = {
        "north": (LANE_CX["north"], SL["north"] - 30),
        "south": (LANE_CX["south"], SL["south"] + 30),
        "east":  (SL["east"] + 30,  LANE_CY["east"]),
        "west":  (SL["west"] - 30,  LANE_CY["west"]),
    }
    for approach, (px, py) in positions.items():
        phase = APPROACH_PHASE[approach]
        color = SIG_CLR[signal_colors.get(phase, "red")]
        cv2.rectangle(canvas, (int(px)-15, int(py)-15),
                               (int(px)+15, int(py)+15), (35,35,35), -1)
        cv2.circle(canvas, (int(px), int(py)), 12, color, -1)
        cv2.circle(canvas, (int(px), int(py)), 12, (155,155,155), 1)
        cv2.putText(canvas, approach[0].upper(),
                    (int(px)-6, int(py)+5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (8,8,8), 1)


def draw_emergency_vehicle(canvas, v: Vehicle, flash_on: bool):
    """
    Ambulance: fluorescent body with a two-tone light bar across the roof.
    The bar alternates red/blue with `flash_on` so it reads as flashing on
    screen — but BOTH colours are always painted somewhere on the vehicle, so
    EmergencyClassifier fires on every frame rather than every other one.
    """
    cx, cy = v.x, v.y
    vw, vh = VW[v.approach], VH[v.approach]
    # Slightly larger than a car, as an ambulance is.
    vw, vh = int(vw * 1.15), int(vh * 1.15)
    x1, y1 = int(cx - vw/2), int(cy - vh/2)
    x2, y2 = int(cx + vw/2), int(cy + vh/2)

    cv2.rectangle(canvas, (x1, y1), (x2, y2), EV_BODY, -1)
    cv2.rectangle(canvas, (x1, y1), (x2, y2), (12, 12, 12), 1)

    first, second = (EV_RED, EV_BLUE) if flash_on else (EV_BLUE, EV_RED)
    if v.approach in ("north", "south"):
        # Vertical vehicle — bar runs left/right across the roof.
        by1, by2 = int(cy - vh * 0.16), int(cy + vh * 0.16)
        mid = (x1 + x2) // 2
        cv2.rectangle(canvas, (x1 + 2, by1), (mid,     by2), first,  -1)
        cv2.rectangle(canvas, (mid,     by1), (x2 - 2, by2), second, -1)
    else:
        # Horizontal vehicle — bar runs top/bottom across the roof.
        bx1, bx2 = int(cx - vw * 0.16), int(cx + vw * 0.16)
        mid = (y1 + y2) // 2
        cv2.rectangle(canvas, (bx1, y1 + 2), (bx2, mid),     first,  -1)
        cv2.rectangle(canvas, (bx1, mid),    (bx2, y2 - 2), second, -1)

    # White cross, so it is unmistakably an ambulance to a human viewer.
    ccx, ccy = int(cx), int(cy)
    arm = max(3, int(min(vw, vh) * 0.18))
    cv2.line(canvas, (ccx - arm, ccy), (ccx + arm, ccy), (255, 255, 255), 2)
    cv2.line(canvas, (ccx, ccy - arm), (ccx, ccy + arm), (255, 255, 255), 2)


def draw_vehicle(canvas, v: Vehicle, flash_on: bool = True):
    if v.is_emergency:
        draw_emergency_vehicle(canvas, v, flash_on)
        return

    cx, cy = v.x, v.y
    vw, vh = VW[v.approach], VH[v.approach]
    x1, y1 = int(cx - vw/2), int(cy - vh/2)
    x2, y2 = int(cx + vw/2), int(cy + vh/2)
    clr = VEH_CLR[v.approach]

    cv2.rectangle(canvas, (x1,y1), (x2,y2), clr, -1)
    cv2.rectangle(canvas, (x1,y1), (x2,y2), (12,12,12), 1)

    ws = (80, 115, 140)
    hl = (210, 210, 130)
    tl = (25, 25, 185)

    if v.approach == "north":
        cv2.rectangle(canvas, (x1+4, y1+6),  (x2-4, y1+15), ws, -1)
        cv2.rectangle(canvas, (x1+2, y1+2),  (x1+7, y1+6),  hl, -1)
        cv2.rectangle(canvas, (x2-7, y1+2),  (x2-2, y1+6),  hl, -1)
        cv2.rectangle(canvas, (x1+2, y2-5),  (x1+7, y2-2),  tl, -1)
        cv2.rectangle(canvas, (x2-7, y2-5),  (x2-2, y2-2),  tl, -1)
    elif v.approach == "south":
        cv2.rectangle(canvas, (x1+4, y2-15), (x2-4, y2-6),  ws, -1)
        cv2.rectangle(canvas, (x1+2, y2-6),  (x1+7, y2-2),  hl, -1)
        cv2.rectangle(canvas, (x2-7, y2-6),  (x2-2, y2-2),  hl, -1)
        cv2.rectangle(canvas, (x1+2, y1+2),  (x1+7, y1+5),  tl, -1)
        cv2.rectangle(canvas, (x2-7, y1+2),  (x2-2, y1+5),  tl, -1)
    elif v.approach == "east":
        cv2.rectangle(canvas, (x2-15, y1+4), (x2-6,  y2-4), ws, -1)
        cv2.rectangle(canvas, (x2-6,  y1+2), (x2-2,  y1+7), hl, -1)
        cv2.rectangle(canvas, (x2-6,  y2-7), (x2-2,  y2-2), hl, -1)
        cv2.rectangle(canvas, (x1+2,  y1+2), (x1+5,  y1+7), tl, -1)
        cv2.rectangle(canvas, (x1+2,  y2-7), (x1+5,  y2-2), tl, -1)
    else:
        cv2.rectangle(canvas, (x1+6,  y1+4), (x1+15, y2-4), ws, -1)
        cv2.rectangle(canvas, (x1+2,  y1+2), (x1+6,  y1+7), hl, -1)
        cv2.rectangle(canvas, (x1+2,  y2-7), (x1+6,  y2-2), hl, -1)
        cv2.rectangle(canvas, (x2-5,  y1+2), (x2-2,  y1+7), tl, -1)
        cv2.rectangle(canvas, (x2-5,  y2-7), (x2-2,  y2-2), tl, -1)


def _ascii(text: str) -> str:
    """cv2.putText renders only ASCII — anything else comes out as '???'."""
    return (text.replace("—", "-").replace("–", "-")
                .replace("→", "->").replace("≤", "<=")
                .replace("≥", ">=")
                .encode("ascii", "replace").decode("ascii"))


def draw_preempt_banner(canvas, phase: str, flash_on: bool):
    """Flashing strip across the top of the frame while preemption is active."""
    bg = (30, 30, 210) if flash_on else (25, 25, 130)
    cv2.rectangle(canvas, (W - 430, 4), (W - 8, 40), bg, -1)
    cv2.rectangle(canvas, (W - 430, 4), (W - 8, 40), (245, 245, 245), 1)
    cv2.putText(canvas, _ascii(f"** EMERGENCY PREEMPTION - {phase} **"),
                (W - 418, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 2)


def draw_hud(canvas, pm, algo_name, reason, sim_t, q_counts, cycle):
    ov = canvas.copy()
    cv2.rectangle(ov, (4,4), (505,115), (0,0,0), -1)
    cv2.addWeighted(ov, 0.55, canvas, 0.45, 0, canvas)
    tc = (215,215,215)
    lines = [
        f"Sim: {sim_t:6.1f}s   Phase:{pm.current_phase}  [{pm.state.name}]  {pm.time_remaining():.1f}s",
        f"Algo  : {algo_name}",
        f"Reason: {reason[:56]}",
        (f"Queue  N:{q_counts.get('north',0):2d}  S:{q_counts.get('south',0):2d}"
         f"  E:{q_counts.get('east',0):2d}  W:{q_counts.get('west',0):2d}"
         f"   cycles:{cycle}"),
    ]
    for i, line in enumerate(lines):
        cv2.putText(canvas, _ascii(line), (10, 26+i*22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, tc, 1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario",  default="balanced",
                        choices=["balanced","morning_rush","evening_rush","asymmetric"])
    parser.add_argument("--algorithm", default="queue_clearing",
                        choices=["fixed","proportional","queue_clearing",
                                 "longest_queue_first"])
    parser.add_argument("--duration",  type=float, default=120.0)
    parser.add_argument("--output",    default="data/videos/synthetic.mp4")
    parser.add_argument("--config",    default="config/default_config.yaml")
    parser.add_argument("--emergency-rate", type=float, default=None,
                        help="Override emergency.arrival_rate (EVs/second per "
                             "approach). The config default is realistic but "
                             "rare; raise it to ~0.02 for demo footage where an "
                             "ambulance shows up every few seconds.")
    parser.add_argument("--no-emergency", action="store_true",
                        help="No emergency vehicles and no preemption.")
    parser.add_argument("--no-hud", action="store_true",
                        help="Omit the baked-in overlay. Use this for footage fed "
                             "to the dashboard, whose own panel would otherwise "
                             "contradict it (different algorithm, different counts).")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    if args.no_emergency:
        config.setdefault("emergency", {})["enabled"] = False
    elif args.emergency_rate is not None:
        config.setdefault("emergency", {})["enabled"] = True
        config["emergency"]["arrival_rate"] = args.emergency_rate

    from src.signals.timing_algorithms import (
        EmergencyPreemptionController, build_controller,
    )
    from src.signals.phase_manager import PhaseManager, SignalState
    from src.simulation.intersection import APPROACH_PHASE as PHASE_OF
    from src.simulation.traffic_generator import TrafficGenerator

    algo = build_controller(args.algorithm, config)
    preemption = algo if isinstance(algo, EmergencyPreemptionController) else None
    pm   = PhaseManager(config, "NS")
    gen  = TrafficGenerator(config, args.scenario, seed=42)
    pm.set_green_duration(algo.green_duration({a:0 for a in APPROACHES}, "NS"))
    sim_t = 0.0

    # Queues of Vehicle objects, one list per approach (index 0 = front)
    queues: dict = {a: [] for a in APPROACHES}

    def on_phase_change(new_phase: str):
        algo.record_served(new_phase)
        q_counts = {a: len(queues[a]) for a in APPROACHES}
        nxt = algo.next_phase(q_counts, new_phase, sim_t)
        pm.request_phase_change(nxt, algo.green_duration(q_counts, nxt))

    pm.on_phase_change(on_phase_change)

    def emergency_phases() -> set:
        return {PHASE_OF[a] for a in APPROACHES
                if any(v.is_emergency for v in queues[a])}

    def service_emergency():
        """Mirror of SimEngine._service_emergency for the rendered video."""
        if preemption is None:
            return
        was = preemption.is_preempting
        preemption.notify_emergency(emergency_phases(), pm.current_phase)
        if preemption.is_preempting:
            target = preemption.target_phase
            if pm.current_phase == target:
                if pm.state == SignalState.GREEN:
                    pm.hold_green(preemption.max_preempt_green)
            else:
                pm.request_phase_change(target, preemption.max_preempt_green)
                pm.truncate_green(preemption.min_green_before_preempt)
        elif was:
            q_counts = {a: len(queues[a]) for a in APPROACHES}
            nxt = algo.next_phase(q_counts, pm.current_phase, sim_t)
            pm.request_phase_change(nxt, algo.green_duration(q_counts, nxt))
            pm.truncate_green(0.0)

    depart_accum = {a: 0.0 for a in APPROACHES}
    DEPART_RATE  = 0.5   # vehicles/second during green

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    writer = cv2.VideoWriter(args.output,
                             cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    total  = int(args.duration * FPS)

    print(f"Generating {args.duration:.0f}s | {total} frames | "
          f"scenario={args.scenario} algo={args.algorithm}")

    for fi in range(total):
        q_counts = {a: len(queues[a]) for a in APPROACHES}

        algo.update_sim_time(sim_t)

        # ── Arrivals ──────────────────────────────────────────────────────
        for approach, n in gen.arrivals_all(DT).items():
            for _ in range(n):
                slot = len(queues[approach])
                if slot < MAX_SLOTS:
                    queues[approach].append(Vehicle(approach, slot))

        # ── Emergency arrivals — jump to the head of the queue ────────────
        for approach in gen.emergency_arrivals(DT):
            ev = Vehicle(approach, 0, is_emergency=True)
            insert_at = 0
            while (insert_at < len(queues[approach])
                   and queues[approach][insert_at].is_emergency):
                insert_at += 1
            queues[approach].insert(insert_at, ev)
            for i, v in enumerate(queues[approach]):
                v.set_slot(i)

        service_emergency()

        # ── Departures (green phase) ───────────────────────────────────────
        sig = pm.get_signal_colors()
        if pm.state == SignalState.GREEN:
            for approach in APPROACHES:
                phase = APPROACH_PHASE[approach]
                if sig.get(phase) == "green" and queues[approach]:
                    front = queues[approach][0]
                    if front.state == "queued":
                        depart_accum[approach] += DEPART_RATE * DT
                        if depart_accum[approach] >= 1.0:
                            depart_accum[approach] -= 1.0
                            front.depart()
                            queues[approach].pop(0)
                            # Slide everyone forward one slot
                            for i, v in enumerate(queues[approach]):
                                v.set_slot(i)
        else:
            for a in APPROACHES:
                depart_accum[a] = 0.0

        # ── Update all vehicle positions ───────────────────────────────────
        for vlist in queues.values():
            for v in vlist:
                v.update()

        pm.step(DT)
        sim_t += DT

        # ── Render ────────────────────────────────────────────────────────
        draw_road(canvas)

        # Light bars alternate at ~4 Hz so the ambulance reads as flashing.
        flash_on = (fi // max(1, FPS // 8)) % 2 == 0

        # Draw queued/sliding/entering vehicles (back to front so front is on
        # top); emergency vehicles go last so they are never occluded.
        for approach in APPROACHES:
            for v in reversed(queues[approach]):
                if not v.is_emergency:
                    draw_vehicle(canvas, v, flash_on)
        for approach in APPROACHES:
            for v in reversed(queues[approach]):
                if v.is_emergency:
                    draw_vehicle(canvas, v, flash_on)

        draw_signals(canvas, pm.get_signal_colors())
        q_display = {a: len(queues[a]) for a in APPROACHES}
        if not args.no_hud:
            draw_hud(canvas, pm, args.algorithm, algo.get_last_reason(),
                     sim_t, q_display, pm.cycle_count)
        if preemption is not None and preemption.is_preempting:
            draw_preempt_banner(canvas, preemption.target_phase, flash_on)

        writer.write(canvas)

        if fi % (FPS * 15) == 0:
            pct = fi / total * 100
            print(f"  [{pct:5.1f}%]  t={sim_t:.0f}s  "
                  f"queues={q_display}  cycles={pm.cycle_count}")

    writer.release()
    print(f"\nVideo  : {args.output}")

    # ── ROI JSON ─────────────────────────────────────────────────────────
    roi = {
        "lane_north": {"approach":"north","polygon":[
            [CX-HALF_R,0],[CX,0],[CX,SL["north"]],[CX-HALF_R,SL["north"]]]},
        "lane_south": {"approach":"south","polygon":[
            [CX,SL["south"]],[CX+HALF_R,SL["south"]],[CX+HALF_R,H],[CX,H]]},
        "lane_east":  {"approach":"east", "polygon":[
            [SL["east"],CY-HALF_R],[W,CY-HALF_R],[W,CY],[SL["east"],CY]]},
        "lane_west":  {"approach":"west", "polygon":[
            [0,CY],[SL["west"],CY],[SL["west"],CY+HALF_R],[0,CY+HALF_R]]},
    }
    roi_path = "config/synthetic_roi.json"
    with open(roi_path, "w") as f:
        json.dump(roi, f, indent=2)
    print(f"ROI    : {roi_path}")
    print(f"\nRun dashboard:")
    print(f"  python scripts/run_dashboard.py {args.output}"
          f" --roi {roi_path} --detector color")


if __name__ == "__main__":
    main()
