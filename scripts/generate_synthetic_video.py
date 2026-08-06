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
# Half the carriageway width = one direction's lane. Wide enough that a vehicle
# fills its lane rather than floating in it, without shrinking the visible
# queue so far that a congested approach no longer reads as congested.
HALF_R    = 66

LANE_CX = {"north": CX - HALF_R // 2, "south": CX + HALF_R // 2}  # 610, 670
LANE_CY = {"east":  CY - HALF_R // 2, "west":  CY + HALF_R // 2}  # 330, 390

SL = {                          # stop-line coordinates
    "north": CY - HALF_R,       # y=300
    "south": CY + HALF_R,       # y=420
    "east":  CX + HALF_R,       # x=700
    "west":  CX - HALF_R,       # x=580
}

# Vehicle classes, after the reference simulation's car / bike / bus / truck.
# `length` runs along the direction of travel, `width` across it. Sprites are
# built facing "up" at these dimensions and rotated per approach.
VEHICLE_TYPES = {
    "car":   {"length": 52, "width": 30, "weight": 0.54},
    "bike":  {"length": 34, "width": 18, "weight": 0.18},
    "bus":   {"length": 92, "width": 36, "weight": 0.13},
    "truck": {"length": 78, "width": 36, "weight": 0.15},
}
EV_TYPE = {"length": 62, "width": 32}

VGAP = 10  # gap between queued vehicles — also keeps detection blobs separate

V_ENTER  = 3.5  # px/frame — entering from edge
V_DEPART = 5.0  # px/frame — clearing the intersection
V_SLIDE  = 4.0  # px/frame — sliding forward in queue

# Longest queue rendered per approach: all the road actually visible upstream
# of that approach's stop line, so a queue fills the frame but never runs off
# the edge. The vertical approaches have less room than the horizontal ones.
MAX_QUEUE_PX = {
    "north": SL["north"] - 12,
    "south": H - SL["south"] - 12,
    "east":  W - SL["east"] - 12,
    "west":  SL["west"] - 12,
}

# Body colours (BGR). Every one is high-saturation on purpose: ColorDetector
# finds vehicles by thresholding HSV saturation, so a realistic grey or white
# car would simply not be detected. Hue is free to vary, saturation is not.
BODY_COLORS = [
    ( 60, 160, 235),   # orange
    ( 60, 200,  70),   # green
    (200,  80,  60),   # blue
    ( 70,  70, 225),   # red
    (210, 190,  55),   # cyan
    ( 55, 210, 215),   # yellow
    (190,  70, 190),   # magenta
    (100, 120, 240),   # coral
]
# Windscreen / windows. Deliberately GREEN-tinted, not blue: a bus's long side
# glazing is a large area, and in blue it read as the blue half of a light bar.
# Paired with the red tail lights that made buses trip EmergencyClassifier's
# balance test. Real automotive glass is green-tinted, so this is both the
# correct-looking and the safe choice. Do not make this blue again.
GLASS      = (95, 125, 78)
TYRE       = (24, 24, 26)
SHADOW     = (14, 14, 14)
HEADLIGHT  = (150, 225, 240)
TAILLIGHT  = (40, 40, 200)

SIG_CLR = {"green": (0,210,0), "yellow": (0,210,210), "red": (20,20,195)}

# Emergency vehicle livery (BGR). The body is a saturated fluorescent lime so
# the saturation-threshold detector picks the whole vehicle up as ONE blob —
# a white ambulance body would fall below the saturation floor and only the
# light bar would be found. The red and blue bars are what EmergencyClassifier
# keys on, and they are deliberately equal in area: the classifier requires the
# two colours to be *balanced*, which is what stops ordinary vehicles (blue
# body, red tail lights) being flagged.
EV_BODY = ( 40, 235, 190)   # fluorescent lime-yellow
EV_RED  = ( 40,  40, 240)
EV_BLUE = (240,  70,  40)

# Sprites face "up" (travelling toward -y) and are rotated with np.rot90, whose
# k counts counter-clockwise quarter turns. Same idea as the reference project
# rotating its PNGs into up/down/left/right folders.
ROT_K = {"north": 2, "south": 0, "east": 1, "west": 3}   # north drives down, etc.
AXIS  = {"north": "v", "south": "v", "east": "h", "west": "h"}

APPROACH_PHASE = {"north":"NS","south":"NS","east":"EW","west":"EW"}
APPROACHES     = ["north","south","east","west"]


# ── Sprite construction ───────────────────────────────────────────────────────
#
# Each vehicle is rendered once into a small offscreen buffer facing "up", then
# rotated for its approach. Drawing in one canonical orientation means the
# detail (windscreen, lights, wheels) is identical in all four directions
# instead of needing four hand-written branches, and it is how the reference
# simulation handles its sprite assets.

def _rounded_rect(img, x1, y1, x2, y2, colour, radius):
    """Filled rounded rectangle — cv2 has no primitive for this."""
    radius = max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    if radius == 0:
        cv2.rectangle(img, (x1, y1), (x2, y2), colour, -1)
        return
    cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), colour, -1)
    cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), colour, -1)
    for cx, cy in ((x1 + radius, y1 + radius), (x2 - radius, y1 + radius),
                   (x1 + radius, y2 - radius), (x2 - radius, y2 - radius)):
        cv2.circle(img, (cx, cy), radius, colour, -1)


def _blank(length: int, width: int):
    """Empty sprite buffer plus its coverage mask, facing up."""
    return (np.zeros((length, width, 3), dtype=np.uint8),
            np.zeros((length, width), dtype=np.uint8))


def _wheels(sprite, mask, length, width, pairs):
    """Dark tyres poking out along both flanks at the given length fractions."""
    tw = max(2, width // 8)
    th = max(3, length // 7)
    for frac in pairs:
        cy = int(length * frac)
        for x1, x2 in ((0, tw), (width - tw, width)):
            cv2.rectangle(sprite, (x1, cy - th // 2), (x2, cy + th // 2), TYRE, -1)
            cv2.rectangle(mask,   (x1, cy - th // 2), (x2, cy + th // 2), 255, -1)


def _sprite_car(colour, length, width):
    sprite, mask = _blank(length, width)
    _rounded_rect(mask, 1, 0, width - 2, length - 1, 255, width // 3)
    _wheels(sprite, mask, length, width, (0.22, 0.78))
    _rounded_rect(sprite, 1, 0, width - 2, length - 1, colour, width // 3)
    # Cabin: one glass block with a slim roof bar through it. Kept small and
    # low-contrast — large bright panels make the car read as a striped flag
    # once the sprite is rotated, rather than as a single vehicle.
    cv2.rectangle(sprite, (4, int(length * 0.24)), (width - 5, int(length * 0.66)), GLASS, -1)
    roof = tuple(min(255, int(c * 1.10)) for c in colour)
    cv2.rectangle(sprite, (4, int(length * 0.40)), (width - 5, int(length * 0.52)), roof, -1)
    cv2.rectangle(sprite, (2, 1), (6, 4), HEADLIGHT, -1)
    cv2.rectangle(sprite, (width - 7, 1), (width - 3, 4), HEADLIGHT, -1)
    cv2.rectangle(sprite, (2, length - 5), (6, length - 2), TAILLIGHT, -1)
    cv2.rectangle(sprite, (width - 7, length - 5), (width - 3, length - 2), TAILLIGHT, -1)
    return sprite, mask


def _sprite_bike(colour, length, width):
    sprite, mask = _blank(length, width)
    _rounded_rect(mask, 2, 0, width - 3, length - 1, 255, width // 3)
    _rounded_rect(sprite, 2, 0, width - 3, length - 1, colour, width // 3)
    # Wheels front and back, inline rather than paired.
    for frac in (0.10, 0.88):
        cy = int(length * frac)
        cv2.rectangle(sprite, (width // 2 - 2, cy - 2), (width // 2 + 2, cy + 2), TYRE, -1)
    # Rider: helmet and shoulders.
    cv2.circle(sprite, (width // 2, int(length * 0.42)), max(2, width // 4), GLASS, -1)
    cv2.rectangle(sprite, (1, int(length * 0.52)), (width - 2, int(length * 0.64)),
                  tuple(min(255, int(c * 0.75)) for c in colour), -1)
    cv2.rectangle(sprite, (width // 2 - 2, 0), (width // 2 + 2, 3), HEADLIGHT, -1)
    return sprite, mask


def _sprite_bus(colour, length, width):
    sprite, mask = _blank(length, width)
    _rounded_rect(mask, 0, 0, width - 1, length - 1, 255, 4)
    _wheels(sprite, mask, length, width, (0.17, 0.62, 0.85))
    _rounded_rect(sprite, 0, 0, width - 1, length - 1, colour, 4)
    # Windscreen, then continuous glazing down both flanks — the long strip of
    # window is what makes a bus read as a bus from above.
    cv2.rectangle(sprite, (3, 3), (width - 4, int(length * 0.13)), GLASS, -1)
    cv2.rectangle(sprite, (2, int(length * 0.20)),
                          (5, int(length * 0.88)), GLASS, -1)
    cv2.rectangle(sprite, (width - 6, int(length * 0.20)),
                          (width - 3, int(length * 0.88)), GLASS, -1)
    # Roof hatches, evenly spaced along the spine.
    roof = tuple(min(255, int(c * 1.12)) for c in colour)
    for y in range(int(length * 0.24), int(length * 0.85), 20):
        cv2.rectangle(sprite, (width // 2 - 4, y), (width // 2 + 4, y + 9), roof, -1)
    # Tail lights kept to the corners rather than a full-width bar — a big red
    # band on a large vehicle is exactly what unbalances the EV classifier.
    cv2.rectangle(sprite, (3, length - 5), (9, length - 2), TAILLIGHT, -1)
    cv2.rectangle(sprite, (width - 10, length - 5), (width - 4, length - 2), TAILLIGHT, -1)
    return sprite, mask


def _sprite_truck(colour, length, width):
    sprite, mask = _blank(length, width)
    _rounded_rect(mask, 0, 0, width - 1, length - 1, 255, 3)
    _wheels(sprite, mask, length, width, (0.16, 0.70, 0.88))
    cab_end = int(length * 0.30)
    # Coloured cab up front, neutral cargo box behind it — the silhouette that
    # reads as "truck" from above.
    _rounded_rect(sprite, 0, 0, width - 1, cab_end, colour, 4)
    cargo = tuple(min(255, int(c * 0.45) + 45) for c in colour)
    cv2.rectangle(sprite, (0, cab_end + 2), (width - 1, length - 1), cargo, -1)
    cv2.rectangle(sprite, (0, cab_end + 2), (width - 1, length - 1), (30, 30, 30), 1)
    # Ribs across the cargo box.
    for y in range(cab_end + 8, length - 4, 9):
        cv2.line(sprite, (1, y), (width - 2, y), (35, 35, 35), 1)
    cv2.rectangle(sprite, (3, 3), (width - 4, int(length * 0.14)), GLASS, -1)
    cv2.rectangle(sprite, (1, 0), (5, 3), HEADLIGHT, -1)
    cv2.rectangle(sprite, (width - 6, 0), (width - 2, 3), HEADLIGHT, -1)
    return sprite, mask


def _sprite_emergency(length, width, flash_on):
    """
    Ambulance: fluorescent body, red/blue light bar, white cross. The bar's two
    halves swap with `flash_on` so it reads as flashing, but both colours are
    always present in equal area so EmergencyClassifier fires on every frame.
    """
    sprite, mask = _blank(length, width)
    _rounded_rect(mask, 0, 0, width - 1, length - 1, 255, 4)
    _wheels(sprite, mask, length, width, (0.18, 0.82))
    _rounded_rect(sprite, 0, 0, width - 1, length - 1, EV_BODY, 4)
    cv2.rectangle(sprite, (3, 3), (width - 4, int(length * 0.16)), GLASS, -1)

    first, second = (EV_RED, EV_BLUE) if flash_on else (EV_BLUE, EV_RED)
    by1, by2 = int(length * 0.30), int(length * 0.42)
    cv2.rectangle(sprite, (1, by1), (width // 2, by2), first, -1)
    cv2.rectangle(sprite, (width // 2, by1), (width - 2, by2), second, -1)

    ccx, ccy = width // 2, int(length * 0.68)
    arm = max(3, width // 4)
    cv2.line(sprite, (ccx - arm, ccy), (ccx + arm, ccy), (255, 255, 255), 3)
    cv2.line(sprite, (ccx, ccy - arm), (ccx, ccy + arm), (255, 255, 255), 3)
    return sprite, mask


_SPRITE_BUILDERS = {
    "car": _sprite_car, "bike": _sprite_bike,
    "bus": _sprite_bus, "truck": _sprite_truck,
}

# Non-emergency sprites never change, so build each (type, colour) once.
_SPRITE_CACHE: dict = {}


def get_sprite(vtype: str, colour_idx: int, approach: str,
               is_emergency: bool, flash_on: bool):
    """Sprite + mask, rotated for the approach's direction of travel."""
    k = ROT_K[approach]
    if is_emergency:
        spec = EV_TYPE
        sprite, mask = _sprite_emergency(spec["length"], spec["width"], flash_on)
        return np.rot90(sprite, k), np.rot90(mask, k)

    key = (vtype, colour_idx, approach)
    if key not in _SPRITE_CACHE:
        spec = VEHICLE_TYPES[vtype]
        sprite, mask = _SPRITE_BUILDERS[vtype](
            BODY_COLORS[colour_idx], spec["length"], spec["width"]
        )
        _SPRITE_CACHE[key] = (np.rot90(sprite, k), np.rot90(mask, k))
    return _SPRITE_CACHE[key]


# ── Vehicle class ─────────────────────────────────────────────────────────────

class Vehicle:
    """Single animated vehicle with entering / queued / sliding / departing states."""

    def __init__(self, approach: str, vtype: str = "car",
                 colour_idx: int = 0, is_emergency: bool = False):
        self.approach     = approach
        self.state        = "entering"
        self.is_emergency = is_emergency
        self.vtype        = "ambulance" if is_emergency else vtype
        self.colour_idx   = colour_idx

        spec = EV_TYPE if is_emergency else VEHICLE_TYPES[vtype]
        self.length = spec["length"]
        self.width  = spec["width"]

        # Start just off the edge of the frame, in this approach's lane.
        if approach == "north":
            self.x, self.y = float(LANE_CX["north"]), float(-self.length)
        elif approach == "south":
            self.x, self.y = float(LANE_CX["south"]), float(H + self.length)
        elif approach == "east":
            self.x, self.y = float(W + self.length), float(LANE_CY["east"])
        else:
            self.x, self.y = float(-self.length), float(LANE_CY["west"])

        self.tx, self.ty = self.x, self.y

    @property
    def box(self):
        """On-screen (width, height) after rotation for this approach."""
        if AXIS[self.approach] == "v":
            return self.width, self.length
        return self.length, self.width

    def set_target(self, tx: float, ty: float):
        """Point the vehicle at a new stop position; queued cars slide to it."""
        self.tx, self.ty = float(tx), float(ty)
        if self.state == "queued":
            self.state = "sliding"

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

    def depart(self):
        """Front vehicle leaves — set straight-through departure."""
        self.state = "departing"
        # Snap to stop-line centre so the exit path is clean
        if   self.approach == "north": self.x, self.y = float(LANE_CX["north"]), float(SL["north"])
        elif self.approach == "south": self.x, self.y = float(LANE_CX["south"]), float(SL["south"])
        elif self.approach == "east":  self.x, self.y = float(SL["east"]),        float(LANE_CY["east"])
        else:                          self.x, self.y = float(SL["west"]),         float(LANE_CY["west"])


# ── Geometry helpers ──────────────────────────────────────────────────────────

def layout_queue(approach: str, vehicles):
    """
    Place every vehicle in an approach's queue, nose-to-tail behind the stop
    line. Unlike a fixed slot grid this accounts for each vehicle's own length,
    so a bus genuinely occupies more road than a motorbike — which is the whole
    point of having vehicle classes.
    """
    offset = 0.0
    for v in vehicles:
        centre = offset + v.length / 2.0
        if approach == "north":
            v.set_target(LANE_CX["north"], SL["north"] - centre)
        elif approach == "south":
            v.set_target(LANE_CX["south"], SL["south"] + centre)
        elif approach == "east":
            v.set_target(SL["east"] + centre, LANE_CY["east"])
        else:
            v.set_target(SL["west"] - centre, LANE_CY["west"])
        offset += v.length + VGAP


def queue_px(vehicles) -> float:
    """Road length a queue already occupies, used to cap on-screen queueing."""
    return sum(v.length + VGAP for v in vehicles)


# ── Drawing ───────────────────────────────────────────────────────────────────

def draw_road(canvas):
    # Grass/verge base, then asphalt, so the junction reads as a place rather
    # than a cross on a black field.
    canvas[:] = (38, 52, 34)
    rd = (58, 58, 60)
    cv2.rectangle(canvas, (0, CY-HALF_R),         (W, CY+HALF_R),         rd, -1)
    cv2.rectangle(canvas, (CX-HALF_R, 0),          (CX+HALF_R, H),          rd, -1)
    cv2.rectangle(canvas, (CX-HALF_R, CY-HALF_R),  (CX+HALF_R, CY+HALF_R), (68,68,70), -1)

    # Kerb lines along the edge of each carriageway.
    kb = (92, 92, 95)
    for y in (CY-HALF_R, CY+HALF_R):
        cv2.line(canvas, (0, y), (CX-HALF_R, y), kb, 2)
        cv2.line(canvas, (CX+HALF_R, y), (W, y), kb, 2)
    for x in (CX-HALF_R, CX+HALF_R):
        cv2.line(canvas, (x, 0), (x, CY-HALF_R), kb, 2)
        cv2.line(canvas, (x, CY+HALF_R), (x, H), kb, 2)

    # Solid centre divider between opposing directions, with dashed lane
    # separators either side — the three-lane look of the reference layout.
    mk = (150, 150, 150)
    dash = (120, 120, 120)
    cv2.line(canvas, (CX, 0), (CX, CY-HALF_R), mk, 2)
    cv2.line(canvas, (CX, CY+HALF_R), (CX, H), mk, 2)
    cv2.line(canvas, (0, CY), (CX-HALF_R, CY), mk, 2)
    cv2.line(canvas, (CX+HALF_R, CY), (W, CY), mk, 2)
    for y in list(range(0, CY-HALF_R, 26)) + list(range(CY+HALF_R, H, 26)):
        cv2.line(canvas, (CX-HALF_R//2, y), (CX-HALF_R//2, y+13), dash, 1)
        cv2.line(canvas, (CX+HALF_R//2, y), (CX+HALF_R//2, y+13), dash, 1)
    for x in list(range(0, CX-HALF_R, 26)) + list(range(CX+HALF_R, W, 26)):
        cv2.line(canvas, (x, CY-HALF_R//2), (x+13, CY-HALF_R//2), dash, 1)
        cv2.line(canvas, (x, CY+HALF_R//2), (x+13, CY+HALF_R//2), dash, 1)

    # Zebra crossings — ladder stripes spanning the full approach lane, set
    # back from the junction so the stop line sits behind them.
    zb = (198, 198, 198)
    bar, step = 9, 17
    for s in range(0, HALF_R - 4, step):
        cv2.rectangle(canvas, (CX-HALF_R+s, SL["north"]-16),
                              (CX-HALF_R+s+bar, SL["north"]-4), zb, -1)
        cv2.rectangle(canvas, (CX+s, SL["south"]+4),
                              (CX+s+bar, SL["south"]+16), zb, -1)
        cv2.rectangle(canvas, (SL["east"]+4, CY-HALF_R+s),
                              (SL["east"]+16, CY-HALF_R+s+bar), zb, -1)
        cv2.rectangle(canvas, (SL["west"]-16, CY+s),
                              (SL["west"]-4, CY+s+bar), zb, -1)

    # Stop lines, one per approach lane
    wh = (240, 240, 240)
    cv2.line(canvas, (CX-HALF_R, SL["north"]), (CX,         SL["north"]), wh, 4)
    cv2.line(canvas, (CX,        SL["south"]), (CX+HALF_R,  SL["south"]), wh, 4)
    cv2.line(canvas, (SL["east"],CY-HALF_R),   (SL["east"], CY),          wh, 4)
    cv2.line(canvas, (SL["west"],CY),          (SL["west"], CY+HALF_R),   wh, 4)

    # Direction-of-travel arrows well back from the junction
    ac = (108, 108, 108)
    cv2.arrowedLine(canvas, (LANE_CX["north"], 100), (LANE_CX["north"],140), ac, 3, tipLength=0.4)
    cv2.arrowedLine(canvas, (LANE_CX["south"], H-100),(LANE_CX["south"],H-140),ac,3,tipLength=0.4)
    cv2.arrowedLine(canvas, (W-100, LANE_CY["east"]), (W-140, LANE_CY["east"]),  ac, 3, tipLength=0.4)
    cv2.arrowedLine(canvas, (100,   LANE_CY["west"]), (140,   LANE_CY["west"]),  ac, 3, tipLength=0.4)


# Signal heads sit on the verge at the near corner of each approach, where a
# real one faces the traffic it controls.
SIGNAL_POS = {
    "north": (CX - HALF_R - 26, SL["north"] - 30),
    "south": (CX + HALF_R + 26, SL["south"] + 30),
    "east":  (SL["east"] + 30,  CY - HALF_R - 26),
    "west":  (SL["west"] - 30,  CY + HALF_R + 26),
}


def draw_signals(canvas, signal_colors: dict, remaining: float = None):
    """
    Three-aspect signal heads with a countdown above each, after the reference
    simulation. The countdown is the time left in the *current* interval for
    the approach being served; approaches on red show their wait instead.
    """
    for approach, (px, py) in SIGNAL_POS.items():
        px, py = int(px), int(py)
        state = signal_colors.get(APPROACH_PHASE[approach], "red")

        # Housing with all three aspects, only the active one lit.
        cv2.rectangle(canvas, (px-13, py-34), (px+13, py+34), (28, 28, 30), -1)
        cv2.rectangle(canvas, (px-13, py-34), (px+13, py+34), (110, 110, 112), 1)
        for i, aspect in enumerate(("red", "yellow", "green")):
            cy = py - 21 + i * 21
            lit = (state == aspect)
            colour = SIG_CLR[aspect] if lit else tuple(int(c * 0.18) for c in SIG_CLR[aspect])
            cv2.circle(canvas, (px, cy), 8, colour, -1)
            if lit:
                cv2.circle(canvas, (px, cy), 11, colour, 1)

        label = approach[0].upper()
        cv2.putText(canvas, label, (px - 5, py + 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, (225, 225, 225), 1)
        if remaining is not None:
            txt = f"{remaining:.0f}"
            cv2.rectangle(canvas, (px-15, py-56), (px+15, py-38), (0, 0, 0), -1)
            (tw, _), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.putText(canvas, txt, (px - tw // 2, py - 43),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


def draw_vehicle(canvas, v: Vehicle, flash_on: bool = True):
    """
    Blit a vehicle's rotated sprite onto the canvas, with a soft drop shadow
    beneath it. The shadow is deliberately dark and unsaturated: it separates
    adjacent vehicles in the saturation mask so ColorDetector keeps counting
    them as distinct blobs instead of merging a queue into one contour.
    """
    sprite, mask = get_sprite(
        v.vtype if not v.is_emergency else "ambulance",
        v.colour_idx, v.approach, v.is_emergency, flash_on,
    )
    sh, sw = mask.shape
    x1 = int(round(v.x - sw / 2.0))
    y1 = int(round(v.y - sh / 2.0))

    # Shadow first, offset down-right.
    sx1, sy1 = x1 + 3, y1 + 3
    cx1, cy1 = max(0, sx1), max(0, sy1)
    cx2, cy2 = min(W, sx1 + sw), min(H, sy1 + sh)
    if cx2 > cx1 and cy2 > cy1:
        sub = mask[cy1 - sy1:cy2 - sy1, cx1 - sx1:cx2 - sx1] > 0
        region = canvas[cy1:cy2, cx1:cx2]
        region[sub] = (region[sub] * 0.35).astype(np.uint8)

    # Then the sprite itself.
    cx1, cy1 = max(0, x1), max(0, y1)
    cx2, cy2 = min(W, x1 + sw), min(H, y1 + sh)
    if cx2 <= cx1 or cy2 <= cy1:
        return
    msub = mask[cy1 - y1:cy2 - y1, cx1 - x1:cx2 - x1] > 0
    ssub = sprite[cy1 - y1:cy2 - y1, cx1 - x1:cx2 - x1]
    canvas[cy1:cy2, cx1:cx2][msub] = ssub[msub]


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

    # Vehicles that have left their queue and are crossing the junction. They
    # used to be dropped the moment they were served, so traffic vanished at
    # the stop line; keeping them alive until they leave the frame is what
    # makes the intersection look like it is actually flowing.
    departing: list = []

    # Vehicle class and colour are drawn from their own RNG so the mix is
    # reproducible and independent of the arrival and emergency streams.
    vtype_rng    = np.random.default_rng(2026)
    TYPE_NAMES   = list(VEHICLE_TYPES)
    TYPE_WEIGHTS = [VEHICLE_TYPES[t]["weight"] for t in TYPE_NAMES]
    TYPE_WEIGHTS = [w / sum(TYPE_WEIGHTS) for w in TYPE_WEIGHTS]

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
                # Cap by road length, not vehicle count, now that a bus
                # occupies far more space than a motorbike.
                if queue_px(queues[approach]) < MAX_QUEUE_PX[approach]:
                    vtype = str(vtype_rng.choice(TYPE_NAMES, p=TYPE_WEIGHTS))
                    queues[approach].append(Vehicle(
                        approach, vtype,
                        int(vtype_rng.integers(len(BODY_COLORS))),
                    ))
                    layout_queue(approach, queues[approach])

        # ── Emergency arrivals — jump to the head of the queue ────────────
        for approach in gen.emergency_arrivals(DT):
            ev = Vehicle(approach, is_emergency=True)
            insert_at = 0
            while (insert_at < len(queues[approach])
                   and queues[approach][insert_at].is_emergency):
                insert_at += 1
            queues[approach].insert(insert_at, ev)
            layout_queue(approach, queues[approach])

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
                            departing.append(queues[approach].pop(0))
                            # Everyone behind rolls forward to close the gap.
                            layout_queue(approach, queues[approach])
        else:
            for a in APPROACHES:
                depart_accum[a] = 0.0

        # ── Update all vehicle positions ───────────────────────────────────
        for vlist in queues.values():
            for v in vlist:
                v.update()
        for v in departing:
            v.update()
        departing[:] = [v for v in departing if not v.is_offscreen()]

        pm.step(DT)
        sim_t += DT

        # ── Render ────────────────────────────────────────────────────────
        draw_road(canvas)

        # Light bars alternate at ~4 Hz so the ambulance reads as flashing.
        flash_on = (fi // max(1, FPS // 8)) % 2 == 0

        # Vehicles crossing the junction sit under the queued traffic, then
        # queues back-to-front, then emergency vehicles last so an ambulance is
        # never occluded by the cars around it.
        for v in departing:
            draw_vehicle(canvas, v, flash_on)
        for approach in APPROACHES:
            for v in reversed(queues[approach]):
                if not v.is_emergency:
                    draw_vehicle(canvas, v, flash_on)
        for approach in APPROACHES:
            for v in reversed(queues[approach]):
                if v.is_emergency:
                    draw_vehicle(canvas, v, flash_on)

        draw_signals(canvas, pm.get_signal_colors(), pm.time_remaining())
        q_display = {a: len(queues[a]) for a in APPROACHES}
        # Both of these are baked-in overlay, so --no-hud must suppress both.
        # Leaving the preemption banner on would put a "PREEMPTING NS" caption
        # in footage the dashboard is independently deciding about, and the two
        # would visibly contradict each other.
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
