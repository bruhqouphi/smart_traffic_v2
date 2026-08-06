import os
import time
from typing import Dict, List, Optional

import cv2
import numpy as np
import pygame

import sys

from src.detection.detector import VehicleDetector
from src.detection.roi_manager import ROIManager
from src.detection.video_input import VideoInput
from src.signals.phase_manager import PhaseManager, SignalState
from src.signals.timing_algorithms import (
    ALGORITHMS,
    EmergencyPreemptionController,
    TimingAlgorithm,
    build_controller,
    emergency_enabled,
)

# Derived from the registry so the dashboard never goes stale as algorithms are
# added. Keys 1..N select algorithms in this order.
ALGORITHM_NAMES = list(ALGORITHMS)
_SIGNAL_RGB = {"red": (255, 0, 0), "green": (0, 255, 0), "yellow": (255, 255, 0)}
_APPROACH_PHASE = {"north": "NS", "south": "NS", "east": "EW", "west": "EW"}
_EV_BOX_RGB = (255, 40, 40)      # emergency detections, vs amber for ordinary
_EV_ALERT_RGB = (255, 235, 60)
_BANNER_H = 34                   # emergency alert band across the top

# Animated junction panel
_JUNCTION_HALF     = 34          # half the carriageway width, in pixels
_VEH_LEN, _VEH_W   = 14, 9       # queued-vehicle marker size
_MAX_LANE_VEHICLES = 9           # more than this will not fit in the panel
_FLOW_SPEED        = 26.0        # px/s that a green-phase queue rolls forward
# Number keys 1..4 → algorithm index 0..3
_ALGO_KEYS = {
    pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3,
}


class Dashboard:
    """
    Pygame real-time dashboard.
    Layout: top-left=video, top-right=signal diagram,
            bottom-left=bar chart, bottom-right=queue history.
    Keys: SPACE=pause, 1..N=switch algorithm, Q=quit.
    """

    def __init__(self, config: dict, video_path: str,
                 roi_path: Optional[str] = None, detector=None):
        self.config = config
        vis = config["visualization"]
        self.W: int = vis["window_width"]
        self.H: int = vis["window_height"]
        self.fps: int = vis["fps"]
        self._colors = vis["colors"]

        pygame.init()
        self.screen = pygame.display.set_mode((self.W, self.H))
        pygame.display.set_caption("Smart Traffic Controller")
        self.clock = pygame.time.Clock()
        self.font_sm = pygame.font.SysFont("monospace", 14)
        self.font_md = pygame.font.SysFont("monospace", 18)
        self.font_lg = pygame.font.SysFont("monospace", 24, bold=True)

        # Quadrant rects
        hw, hh = self.W // 2, self.H // 2
        self.r_video = pygame.Rect(0, 0, hw, hh)
        self.r_signal = pygame.Rect(hw, 0, hw, hh)
        self.r_bar = pygame.Rect(0, hh, hw, hh)
        self.r_graph = pygame.Rect(hw, hh, hw, hh)

        # Algorithm / phase state — default to longest_queue_first (the tuned
        # controller) when present, else the last registered algorithm.
        self.algo_idx: int = (
            ALGORITHM_NAMES.index("longest_queue_first")
            if "longest_queue_first" in ALGORITHM_NAMES
            else len(ALGORITHM_NAMES) - 1
        )
        self.algorithm: TimingAlgorithm = build_controller(
            ALGORITHM_NAMES[self.algo_idx], config
        )
        self.emergency_on = emergency_enabled(config)
        self.phase_manager = PhaseManager(config, "NS")
        self.phase_manager.set_green_duration(
            self.algorithm.green_duration({}, "NS")
        )
        self.phase_manager.on_phase_change(self._on_phase_change)

        # Approaches currently showing an emergency vehicle, and a running count
        # of preemptions triggered during the session.
        self.emergency_approaches: set = set()
        self.preemption_count = 0

        # Rolling offset that makes a green phase's queue visibly creep toward
        # the junction. Purely cosmetic — it never feeds back into the model.
        self._flow_offset = 0.0

        # Video
        self.video = VideoInput(
            video_path, frame_skip=config["detection"]["frame_skip"]
        )
        self._frame: Optional[np.ndarray] = None
        self._vid_w = max(self.video.width, 1)
        self._vid_h = max(self.video.height, 1)

        # Detection — accept injected detector or fall back to YOLO
        if detector is not None:
            self.detector = detector
        else:
            self.detector = VehicleDetector(config["detection"])
        self.detections = []

        # ROI. Without one, per-approach counts cannot be measured and fall back
        # to an even split of the total detections — which is NOT real data.
        self.roi_manager: Optional[ROIManager] = None
        if roi_path and os.path.exists(roi_path):
            self.roi_manager = ROIManager.from_file(roi_path)
        self._roi_missing = self.roi_manager is None
        if self._roi_missing:
            print(
                "WARNING: no ROI loaded — per-approach queue counts are ESTIMATED "
                "(total split evenly across approaches), not measured. Pass "
                "--roi config/synthetic_roi.json for real per-lane counts.",
                file=sys.stderr,
            )

        self.queues: Dict[str, int] = {a: 0 for a in ("north", "south", "east", "west")}
        self.queue_history: List[Dict[str, int]] = []
        self._max_history = 100
        self._sim_time = 0.0
        self.paused = False
        self._last_wall_time: float = time.perf_counter()
        self._detect_counter: int = 0
        self._detect_every: int = 3  # run YOLO every 3rd frame

    # ------------------------------------------------------------------
    def _c(self, name: str):
        return tuple(self._colors[name])

    @property
    def preemption(self) -> Optional[EmergencyPreemptionController]:
        algo = self.algorithm
        return algo if isinstance(algo, EmergencyPreemptionController) else None

    @property
    def is_preempting(self) -> bool:
        p = self.preemption
        return p is not None and p.is_preempting

    def _on_phase_change(self, new_phase: str):
        self.algorithm.record_served(new_phase)
        next_p = self.algorithm.next_phase(self.queues, new_phase, self._sim_time)
        duration = self.algorithm.green_duration(self.queues, next_p)
        self.phase_manager.request_phase_change(next_p, duration)

    def _switch_algorithm(self, idx: int):
        self.algo_idx = idx
        self.algorithm = build_controller(ALGORITHM_NAMES[idx], self.config)
        self.phase_manager = PhaseManager(self.config, "NS")
        g = self.algorithm.green_duration(self.queues, "NS")
        self.phase_manager.set_green_duration(g)
        self.phase_manager.on_phase_change(self._on_phase_change)

    def _service_emergency(self):
        """
        Drive preemption from what the detector sees. Same sequence as
        SimEngine._service_emergency — the difference is only where the
        emergency signal comes from: ROI detections instead of the queue model.
        """
        preemption = self.preemption
        if preemption is None:
            return

        phases = {
            _APPROACH_PHASE[a]
            for a in self.emergency_approaches
            if a in _APPROACH_PHASE
        }
        pm = self.phase_manager
        was = preemption.is_preempting
        if preemption.notify_emergency(phases, pm.current_phase):
            self.preemption_count += 1

        if preemption.is_preempting:
            target = preemption.target_phase
            if pm.current_phase == target:
                if pm.state == SignalState.GREEN:
                    pm.hold_green(preemption.max_preempt_green)
            else:
                pm.request_phase_change(target, preemption.max_preempt_green)
                pm.truncate_green(preemption.min_green_before_preempt)
        elif was:
            next_p = self.algorithm.next_phase(
                self.queues, pm.current_phase, self._sim_time
            )
            pm.request_phase_change(
                next_p, self.algorithm.green_duration(self.queues, next_p)
            )
            pm.truncate_green(0.0)

    # ------------------------------------------------------------------
    def _process_frame(self):
        frame = self.video.read()
        if frame is None:
            return
        self._frame = frame
        self._vid_w = max(frame.shape[1], 1)
        self._vid_h = max(frame.shape[0], 1)
        self.detections = self.detector.detect(frame)
        if self.roi_manager:
            self.queues = self.roi_manager.count_vehicles_per_approach(self.detections)
            self.emergency_approaches = self.roi_manager.emergency_approaches(
                self.detections
            )
        else:
            total = len(self.detections)
            per, rem = divmod(total, 4)
            for i, a in enumerate(("north", "south", "east", "west")):
                self.queues[a] = per + (1 if i < rem else 0)
            # Without an ROI there is no way to say which approach an emergency
            # vehicle is on, so preemption cannot be targeted and stays off.
            self.emergency_approaches = set()

    # ------------------------------------------------------------------
    def _draw_video(self):
        r = self.r_video
        if self._frame is not None:
            resized = cv2.resize(self._frame, (r.width, r.height))
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            sx = r.width / self._vid_w
            sy = r.height / self._vid_h
            # ROI overlays
            if self.roi_manager:
                for poly in self.roi_manager.get_polygons_for_display().values():
                    scaled = [(int(x * sx), int(y * sy)) for x, y in poly]
                    cv2.polylines(rgb, [np.array(scaled)], True, (0, 255, 100), 2)
            # Detection boxes — emergency vehicles in red, everything else amber
            for det in self.detections:
                x1 = int(det.x1 * sx); y1 = int(det.y1 * sy)
                x2 = int(det.x2 * sx); y2 = int(det.y2 * sy)
                if det.is_emergency:
                    cv2.rectangle(rgb, (x1, y1), (x2, y2), _EV_BOX_RGB, 3)
                    cv2.putText(rgb, "EMERGENCY", (x1, max(12, y1 - 5)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, _EV_BOX_RGB, 1)
                else:
                    cv2.rectangle(rgb, (x1, y1), (x2, y2), (255, 200, 0), 2)
            surf = pygame.surfarray.make_surface(rgb.transpose(1, 0, 2))
            self.screen.blit(surf, r.topleft)
            if self._roi_missing:
                warn = self.font_sm.render(
                    "NO ROI - counts ESTIMATED", True, (255, 80, 80))
                bg = pygame.Surface((warn.get_width() + 8, warn.get_height() + 4))
                bg.set_alpha(180)
                bg.fill((0, 0, 0))
                self.screen.blit(bg, (r.left + 4, r.top + 4))
                self.screen.blit(warn, (r.left + 8, r.top + 6))
        else:
            pygame.draw.rect(self.screen, (20, 20, 20), r)
            lbl = self.font_md.render("No Video", True, (200, 200, 200))
            self.screen.blit(lbl, (r.centerx - lbl.get_width() // 2,
                                   r.centery - lbl.get_height() // 2))
        pygame.draw.rect(self.screen, (80, 80, 80), r, 1)

    def _draw_junction(self, r):
        """
        Live top-down view of the junction: roads, signal heads and one queued
        vehicle per detected vehicle on each approach.

        This is a *visualisation of measured state*, not a second simulation.
        The queue lengths come straight from the ROI counts, and the flow
        offset only animates vehicles rolling forward while their phase is
        green — nothing here feeds back into the controller.
        """
        pm = self.phase_manager
        colours = pm.get_signal_colors()
        cx, cy = r.centerx, r.centery + 14
        half = _JUNCTION_HALF

        # Verge, carriageways, junction box
        pygame.draw.rect(self.screen, (34, 44, 32), r)
        pygame.draw.rect(self.screen, (56, 56, 58), (r.left, cy - half, r.width, half * 2))
        pygame.draw.rect(self.screen, (56, 56, 58), (cx - half, r.top, half * 2, r.height))
        pygame.draw.rect(self.screen, (66, 66, 68),
                         (cx - half, cy - half, half * 2, half * 2))

        # Centre dividers, dashed back from the junction
        for x in range(r.left, cx - half, 14):
            pygame.draw.line(self.screen, (120, 120, 120), (x, cy), (x + 7, cy), 1)
        for x in range(cx + half, r.right, 14):
            pygame.draw.line(self.screen, (120, 120, 120), (x, cy), (x + 7, cy), 1)
        for y in range(r.top, cy - half, 14):
            pygame.draw.line(self.screen, (120, 120, 120), (cx, y), (cx, y + 7), 1)
        for y in range(cy + half, r.bottom, 14):
            pygame.draw.line(self.screen, (120, 120, 120), (cx, y), (cx, y + 7), 1)

        # Stop lines
        for a, seg in (
            ("north", ((cx - half, cy - half), (cx, cy - half))),
            ("south", ((cx, cy + half), (cx + half, cy + half))),
            ("east",  ((cx + half, cy - half), (cx + half, cy))),
            ("west",  ((cx - half, cy), (cx - half, cy + half))),
        ):
            pygame.draw.line(self.screen, (225, 225, 225), seg[0], seg[1], 2)

        # Queued vehicles, one per detected vehicle, nose-to-tail behind the
        # stop line. Green phases get a rolling offset so traffic visibly moves.
        step = _VEH_LEN + 4
        for approach in ("north", "south", "east", "west"):
            phase = _APPROACH_PHASE[approach]
            moving = colours.get(phase) == "green"
            flow = self._flow_offset if moving else 0.0
            has_ev = approach in self.emergency_approaches
            n = min(self.queues.get(approach, 0), _MAX_LANE_VEHICLES)
            lane = half // 2
            for i in range(n):
                d = 6 + i * step + flow
                if approach == "north":
                    rect = pygame.Rect(0, 0, _VEH_W, _VEH_LEN)
                    rect.center = (cx - lane, cy - half - d)
                elif approach == "south":
                    rect = pygame.Rect(0, 0, _VEH_W, _VEH_LEN)
                    rect.center = (cx + lane, cy + half + d)
                elif approach == "east":
                    rect = pygame.Rect(0, 0, _VEH_LEN, _VEH_W)
                    rect.center = (cx + half + d, cy - lane)
                else:
                    rect = pygame.Rect(0, 0, _VEH_LEN, _VEH_W)
                    rect.center = (cx - half - d, cy + lane)
                if not r.contains(rect):
                    break
                # The emergency vehicle is at the head of its queue, which is
                # exactly where the queue model puts it.
                if has_ev and i == 0:
                    pygame.draw.rect(self.screen, _EV_BOX_RGB, rect, border_radius=3)
                    pygame.draw.rect(self.screen, (255, 255, 255), rect, 1, border_radius=3)
                else:
                    body = self._c("bar_ns") if phase == "NS" else self._c("bar_ew")
                    pygame.draw.rect(self.screen, body, rect, border_radius=3)
                    pygame.draw.rect(self.screen, (20, 20, 20), rect, 1, border_radius=3)

        # Signal heads on the near corner of each approach
        heads = {
            "north": (cx - half - 16, cy - half - 18),
            "south": (cx + half + 16, cy + half + 18),
            "east":  (cx + half + 18, cy - half - 16),
            "west":  (cx - half - 18, cy + half + 16),
        }
        for approach, (hx, hy) in heads.items():
            state = colours.get(_APPROACH_PHASE[approach], "red")
            pygame.draw.rect(self.screen, (26, 26, 28), (hx - 7, hy - 19, 14, 38),
                             border_radius=3)
            pygame.draw.rect(self.screen, (110, 110, 112), (hx - 7, hy - 19, 14, 38),
                             1, border_radius=3)
            for j, aspect in enumerate(("red", "yellow", "green")):
                lit = state == aspect
                base = _SIGNAL_RGB[aspect]
                col = base if lit else tuple(int(c * 0.20) for c in base)
                pygame.draw.circle(self.screen, col, (hx, hy - 12 + j * 12), 4)
            lbl = self.font_sm.render(approach[0].upper(), True, (225, 225, 225))
            self.screen.blit(lbl, (hx - lbl.get_width() // 2, hy + 20))

    def _draw_signal_diagram(self):
        r = self.r_signal
        self._draw_junction(r)
        pm = self.phase_manager

        # Info lines
        lines = [
            f"Phase : {pm.current_phase}  ({pm.state.name})",
            f"Time  : {pm.time_remaining():.1f}s remaining",
            f"Algo  : {ALGORITHM_NAMES[self.algo_idx]}",
            f"Cycle : {pm.cycle_count}",
        ]
        if self.emergency_on:
            p = self.preemption
            status = (
                f"PREEMPTING {p.target_phase}" if self.is_preempting else "armed"
            )
            lines.append(f"EVP   : {status}  ({self.preemption_count} total)")
        # The emergency banner occupies the top of the window, so push the
        # readout clear of it rather than letting it cover the phase line.
        y = r.top + (_BANNER_H + 6 if self.is_preempting else 8)

        # Dim strip behind the text — the junction is drawn underneath it and
        # light-grey road on light-grey glyphs is unreadable.
        panel = pygame.Surface((248, len(lines) * 18 + 10))
        panel.set_alpha(185)
        panel.fill((0, 0, 0))
        self.screen.blit(panel, (r.left + 4, y - 5))

        for line in lines:
            colour = (
                _EV_ALERT_RGB
                if line.startswith("EVP") and self.is_preempting
                else (210, 210, 210)
            )
            self.screen.blit(self.font_sm.render(line, True, colour),
                             (r.left + 8, y))
            y += 18

        # Decision line and key hints, on their own dim strip for the same
        # reason as the readout above.
        foot = pygame.Surface((r.width - 8, 38))
        foot.set_alpha(185)
        foot.fill((0, 0, 0))
        self.screen.blit(foot, (r.left + 4, r.bottom - 40))

        reason = self.algorithm.get_last_reason()[:68]
        reason_colour = _EV_ALERT_RGB if self.is_preempting else (150, 220, 150)
        self.screen.blit(self.font_sm.render(reason, True, reason_colour),
                         (r.left + 8, r.bottom - 36))
        hint = f"SPACE=pause  1-{len(ALGORITHM_NAMES)}=algo  Q=quit"
        self.screen.blit(self.font_sm.render(hint, True, (130, 130, 130)),
                         (r.left + 8, r.bottom - 18))
        pygame.draw.rect(self.screen, (80, 80, 80), r, 1)

    def _draw_bar_chart(self):
        r = self.r_bar
        pygame.draw.rect(self.screen, (20, 20, 20), r)
        self.screen.blit(
            self.font_sm.render("Queue Lengths (vehicles)", True, (200, 200, 200)),
            (r.left + 8, r.top + 6),
        )
        approaches = ["north", "south", "east", "west"]
        bar_colors = [
            self._c("bar_ns"), self._c("bar_ns"),
            self._c("bar_ew"), self._c("bar_ew"),
        ]
        max_q = max(max(self.queues.values(), default=1), 1)
        slot_w = r.width // len(approaches)
        bar_w = max(slot_w - 20, 10)
        max_bar_h = r.height - 55

        for i, (approach, color) in enumerate(zip(approaches, bar_colors)):
            q = self.queues.get(approach, 0)
            bar_h = int((q / max_q) * max_bar_h)
            x = r.left + i * slot_w + (slot_w - bar_w) // 2
            y = r.bottom - 35 - bar_h
            pygame.draw.rect(self.screen, color, (x, y, bar_w, bar_h))
            lbl = self.font_sm.render(approach[0].upper(), True, (200, 200, 200))
            self.screen.blit(lbl, (x + bar_w // 2 - lbl.get_width() // 2, r.bottom - 28))
            num = self.font_sm.render(str(q), True, (230, 230, 230))
            self.screen.blit(num, (x + bar_w // 2 - num.get_width() // 2,
                                   max(r.top + 25, y - 18)))
        pygame.draw.rect(self.screen, (80, 80, 80), r, 1)

    def _draw_queue_history(self):
        r = self.r_graph
        pygame.draw.rect(self.screen, (15, 15, 15), r)
        self.screen.blit(
            self.font_sm.render("Total Queue History", True, (200, 200, 200)),
            (r.left + 8, r.top + 6),
        )
        history = self.queue_history[-self._max_history:]
        if len(history) < 2:
            pygame.draw.rect(self.screen, (80, 80, 80), r, 1)
            return

        totals = [sum(h.values()) for h in history]
        max_val = max(max(totals), 1)
        pl = r.left + 10; pr = r.right - 10
        pt = r.top + 28; pb = r.bottom - 18
        pw = pr - pl; ph = pb - pt
        n = len(totals)
        points = [
            (pl + int(i / (n - 1) * pw), pb - int(v / max_val * ph))
            for i, v in enumerate(totals)
        ]
        pygame.draw.lines(self.screen, self._c("bar_ew"), False, points, 2)
        # y-axis max label
        self.screen.blit(
            self.font_sm.render(str(max_val), True, (150, 150, 150)),
            (pl, pt),
        )
        pygame.draw.rect(self.screen, (80, 80, 80), r, 1)

    def _draw_emergency_banner(self):
        """Flashing full-width alert across the top while preemption is active."""
        if not self.is_preempting:
            return
        # ~3 Hz flash, driven by wall clock so it is independent of frame rate.
        on = int(time.perf_counter() * 3) % 2 == 0
        approaches = ", ".join(sorted(self.emergency_approaches)).upper()
        target = self.preemption.target_phase
        text = f"EMERGENCY VEHICLE  {approaches or target}  -  PREEMPTING {target}"

        band = pygame.Rect(0, 0, self.W, _BANNER_H)
        pygame.draw.rect(self.screen, (190, 0, 0) if on else (95, 0, 0), band)
        pygame.draw.rect(self.screen, _EV_ALERT_RGB, band, 2)
        label = self.font_lg.render(text, True, (255, 255, 255))
        self.screen.blit(
            label, (self.W // 2 - label.get_width() // 2,
                    band.centery - label.get_height() // 2)
        )

    # ------------------------------------------------------------------
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        self.paused = not self.paused
                    elif event.key in _ALGO_KEYS:
                        idx = _ALGO_KEYS[event.key]
                        if idx < len(ALGORITHM_NAMES):
                            self._switch_algorithm(idx)

            # Wall-clock dt so signal timing is correct regardless of YOLO speed
            now = time.perf_counter()
            dt = now - self._last_wall_time
            self._last_wall_time = now

            if not self.paused:
                # Only run YOLO every _detect_every frames to reduce CPU load
                self._detect_counter += 1
                if self._detect_counter % self._detect_every == 0:
                    self._process_frame()

                self._sim_time += dt
                self.algorithm.update_sim_time(self._sim_time)
                self._service_emergency()
                self.phase_manager.step(dt)
                # Vehicles roll forward one slot then reset, so a served
                # approach reads as flowing rather than frozen.
                self._flow_offset -= _FLOW_SPEED * dt
                if self._flow_offset <= -(_VEH_LEN + 4):
                    self._flow_offset += _VEH_LEN + 4
                self.queue_history.append(dict(self.queues))
                if len(self.queue_history) > self._max_history:
                    self.queue_history.pop(0)

            self.screen.fill(self._c("background"))
            self._draw_video()
            self._draw_signal_diagram()
            self._draw_bar_chart()
            self._draw_queue_history()
            self._draw_emergency_banner()

            if self.paused:
                # Centred over the video quadrant, not the window — the window
                # centre lands on the signal panel's phase/time readout.
                ps = self.font_lg.render("PAUSED", True, (255, 200, 0))
                px = self.r_video.centerx - ps.get_width() // 2
                bg = pygame.Surface((ps.get_width() + 16, ps.get_height() + 8))
                bg.set_alpha(190)
                bg.fill((0, 0, 0))
                self.screen.blit(bg, (px - 8, 4))
                self.screen.blit(ps, (px, 8))

            pygame.display.flip()
            self.clock.tick(self.fps)

        pygame.quit()
        self.video.release()
