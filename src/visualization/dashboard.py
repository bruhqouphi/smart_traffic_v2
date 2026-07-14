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
    QueueClearingAlgorithm,
    TimingAlgorithm,
    get_algorithm,
)

# Derived from the registry so the dashboard never goes stale as algorithms are
# added. Keys 1..N select algorithms in this order.
ALGORITHM_NAMES = list(ALGORITHMS)
_SIGNAL_RGB = {"red": (255, 0, 0), "green": (0, 255, 0), "yellow": (255, 255, 0)}
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
        self.algorithm: TimingAlgorithm = get_algorithm(
            ALGORITHM_NAMES[self.algo_idx], config
        )
        self.phase_manager = PhaseManager(config, "NS")
        self.phase_manager.set_green_duration(
            self.algorithm.green_duration({}, "NS")
        )
        self.phase_manager.on_phase_change(self._on_phase_change)

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

    def _on_phase_change(self, new_phase: str):
        if isinstance(self.algorithm, QueueClearingAlgorithm):
            self.algorithm.record_served(new_phase)
        next_p = self.algorithm.next_phase(self.queues, new_phase, self._sim_time)
        duration = self.algorithm.green_duration(self.queues, next_p)
        self.phase_manager.request_phase_change(next_p, duration)

    def _switch_algorithm(self, idx: int):
        self.algo_idx = idx
        self.algorithm = get_algorithm(ALGORITHM_NAMES[idx], self.config)
        self.phase_manager = PhaseManager(self.config, "NS")
        g = self.algorithm.green_duration(self.queues, "NS")
        self.phase_manager.set_green_duration(g)
        self.phase_manager.on_phase_change(self._on_phase_change)

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
        else:
            total = len(self.detections)
            per, rem = divmod(total, 4)
            for i, a in enumerate(("north", "south", "east", "west")):
                self.queues[a] = per + (1 if i < rem else 0)

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
            # Detection boxes
            for det in self.detections:
                x1 = int(det.x1 * sx); y1 = int(det.y1 * sy)
                x2 = int(det.x2 * sx); y2 = int(det.y2 * sy)
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

    def _draw_signal_diagram(self):
        r = self.r_signal
        pygame.draw.rect(self.screen, (25, 25, 25), r)
        pm = self.phase_manager
        colors_map = pm.get_signal_colors()
        cx, cy = r.centerx, r.centery
        road_w = 40

        pygame.draw.rect(self.screen, (55, 55, 55),
                         (r.left, cy - road_w // 2, r.width, road_w))
        pygame.draw.rect(self.screen, (55, 55, 55),
                         (cx - road_w // 2, r.top, road_w, r.height))

        off = 65
        positions = {
            "north": (cx, cy - off),
            "south": (cx, cy + off),
            "east": (cx + off, cy),
            "west": (cx - off, cy),
        }
        approach_phase = {"north": "NS", "south": "NS", "east": "EW", "west": "EW"}
        for approach, pos in positions.items():
            color = _SIGNAL_RGB[colors_map[approach_phase[approach]]]
            pygame.draw.circle(self.screen, color, pos, 13)
            pygame.draw.circle(self.screen, (200, 200, 200), pos, 13, 2)
            lbl = self.font_sm.render(approach[0].upper(), True, (230, 230, 230))
            dx = -22 if approach in ("east", "west") else 0
            dy = -28 if approach == "north" else (16 if approach == "south" else -7)
            self.screen.blit(lbl, (pos[0] + dx, pos[1] + dy))

        # Info lines
        lines = [
            f"Phase : {pm.current_phase}  ({pm.state.name})",
            f"Time  : {pm.time_remaining():.1f}s remaining",
            f"Algo  : {ALGORITHM_NAMES[self.algo_idx]}",
            f"Cycle : {pm.cycle_count}",
        ]
        y = r.top + 8
        for line in lines:
            self.screen.blit(self.font_sm.render(line, True, (210, 210, 210)),
                             (r.left + 8, y))
            y += 18

        reason = self.algorithm.get_last_reason()[:68]
        self.screen.blit(self.font_sm.render(reason, True, (150, 220, 150)),
                         (r.left + 8, r.bottom - 32))
        hint = f"SPACE=pause  1-{len(ALGORITHM_NAMES)}=algo  Q=quit"
        self.screen.blit(self.font_sm.render(hint, True, (100, 100, 100)),
                         (r.left + 8, r.bottom - 14))
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
                if isinstance(self.algorithm, QueueClearingAlgorithm):
                    self.algorithm.update_sim_time(self._sim_time)
                self.phase_manager.step(dt)
                self.queue_history.append(dict(self.queues))
                if len(self.queue_history) > self._max_history:
                    self.queue_history.pop(0)

            self.screen.fill(self._c("background"))
            self._draw_video()
            self._draw_signal_diagram()
            self._draw_bar_chart()
            self._draw_queue_history()

            if self.paused:
                ps = self.font_lg.render("PAUSED", True, (255, 200, 0))
                self.screen.blit(ps, (self.W // 2 - ps.get_width() // 2, 8))

            pygame.display.flip()
            self.clock.tick(self.fps)

        pygame.quit()
        self.video.release()
