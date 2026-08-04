from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set

import numpy as np

MOVEMENTS = ("through", "left", "right")

# Which signal phase serves each approach. NS and EW are the two phases.
APPROACH_PHASE = {"north": "NS", "south": "NS", "east": "EW", "west": "EW"}

# With no `turning:` block every vehicle goes straight and discharges at full
# saturation flow — the behaviour of the model before turns were added.
DEFAULT_SHARES = {"through": 1.0, "left": 0.0, "right": 0.0}


@dataclass
class Vehicle:
    vehicle_id: int
    approach: str
    arrival_time: float
    departure_time: Optional[float] = None
    movement: str = "through"
    is_emergency: bool = False

    @property
    def wait_time(self) -> Optional[float]:
        if self.departure_time is None:
            return None
        return self.departure_time - self.arrival_time


class TurningMix:
    """
    How arriving vehicles split across through/left/right, and how much green
    each movement costs.

    Ghana drives on the right, so a permitted left turn must yield to opposing
    through traffic and discharges well below saturation flow; a right turn is
    only mildly slowed. Both are expressed as HCM-style saturation-flow
    adjustment factors in [0, 1].
    """

    def __init__(self, config: Optional[dict] = None, seed: int = 0):
        cfg = config or {}

        shares = {m: float(cfg.get(m, DEFAULT_SHARES[m])) for m in MOVEMENTS}
        if any(s < 0 for s in shares.values()):
            raise ValueError("turning shares must not be negative")
        total = sum(shares.values())
        if total <= 0:
            raise ValueError("turning shares must sum to a positive number")
        # Normalise so the shares are a probability distribution even if the
        # config author wrote percentages or numbers that do not quite sum to 1.
        self.shares = {m: s / total for m, s in shares.items()}

        self.factors = {
            "through": 1.0,
            "left": float(cfg.get("left_adjustment", 1.0)),
            "right": float(cfg.get("right_adjustment", 1.0)),
        }
        for movement, factor in self.factors.items():
            if not 0.0 < factor <= 1.0:
                raise ValueError(
                    f"{movement} saturation-flow adjustment must be in (0, 1], got {factor}"
                )

        self._rng = np.random.default_rng(seed)
        self._probs = [self.shares[m] for m in MOVEMENTS]

    def sample(self, n: int) -> List[str]:
        """Draw n movements from the configured split."""
        if n <= 0:
            return []
        return list(self._rng.choice(MOVEMENTS, size=n, p=self._probs))

    @property
    def adjustment(self) -> float:
        """
        Share-weighted saturation-flow adjustment: effective flow / saturation
        flow. 1.0 when every vehicle goes straight.
        """
        return sum(self.shares[m] * self.factors[m] for m in MOVEMENTS)


class ApproachQueue:
    def __init__(
        self,
        approach: str,
        saturation_flow: float = 1800.0,
        capacity: Optional[int] = None,
        movement_factors: Optional[Dict[str, float]] = None,
    ):
        self.approach = approach
        self.saturation_flow = saturation_flow
        # Storage limit of the upstream link, in vehicles. None = unlimited.
        self.capacity = capacity
        self.movement_factors = dict(movement_factors or {})
        # Seconds of green one straight-through vehicle occupies.
        self._base_service_time = 3600.0 / saturation_flow
        self._queue: List[Vehicle] = []
        self._next_id = 0
        self._green_credit: float = 0.0  # seconds of discharge time banked
        self.blocked = 0  # arrivals refused because the link was already full

    def service_time(self, vehicle: Vehicle) -> float:
        """
        Green time this vehicle occupies. A turning vehicle discharges at only
        `factor` of saturation flow, so it costs proportionally more — and
        because the approach is a single queue, it holds up everyone behind it.
        """
        factor = self.movement_factors.get(vehicle.movement, 1.0)
        return self._base_service_time / factor

    @property
    def is_full(self) -> bool:
        return self.capacity is not None and len(self._queue) >= self.capacity

    def arrive(self, n: int, t: float, movements: Optional[Sequence[str]] = None) -> int:
        """
        Queue up to n vehicles. Returns how many were turned away because the
        approach had no storage left (spillback into the upstream link).
        """
        accepted = n
        if self.capacity is not None:
            accepted = max(0, min(n, self.capacity - len(self._queue)))

        for i in range(accepted):
            movement = movements[i] if movements is not None else "through"
            self._queue.append(Vehicle(self._next_id, self.approach, t, movement=movement))
            self._next_id += 1

        blocked = n - accepted
        self.blocked += blocked
        return blocked

    def arrive_emergency(self, t: float) -> Vehicle:
        """
        Queue one emergency vehicle at the head of the approach.

        Two departures from ordinary arrivals, both deliberate:

        * **It jumps the queue.** Ordinary traffic pulls aside for a siren, so
          an EV reaches the stop line ahead of the vehicles that arrived before
          it. This is the priority-scheduling tier of the queue model — the
          signal-level preemption sits on top of it. EVs already waiting keep
          their relative order (FIFO among equals).
        * **It ignores `queue_capacity`.** An EV is never turned away as
          spillback; it uses the shoulder or the opposing lane. Accepting it
          unconditionally also keeps EV wait time measurable in oversaturated
          runs, where an EV would otherwise simply vanish from the metrics.
        """
        vehicle = Vehicle(
            self._next_id, self.approach, t, movement="through", is_emergency=True
        )
        self._next_id += 1
        insert_at = 0
        while insert_at < len(self._queue) and self._queue[insert_at].is_emergency:
            insert_at += 1
        self._queue.insert(insert_at, vehicle)
        return vehicle

    @property
    def has_emergency(self) -> bool:
        return any(v.is_emergency for v in self._queue)

    @property
    def emergency_count(self) -> int:
        return sum(1 for v in self._queue if v.is_emergency)

    def depart(self, dt: float, t: float) -> List[Vehicle]:
        self._green_credit += dt
        departed = []
        while self._queue and self._green_credit >= self.service_time(self._queue[0]):
            v = self._queue.pop(0)
            self._green_credit -= self.service_time(v)
            v.departure_time = t
            departed.append(v)
        if not self._queue:
            # An empty approach banks nothing — unused green is lost, since the
            # next arrival still has to start from rest.
            self._green_credit = 0.0
        return departed

    @property
    def length(self) -> int:
        return len(self._queue)


class Intersection:
    """
    Queue model for a 4-way intersection.
    NS phase serves north+south simultaneously; EW serves east+west.
    """

    def __init__(self, config: dict, seed: int = 0):
        t = config["timing"]
        self.startup_lost = float(t["startup_lost_time"])
        self.headway = float(t["headway"])
        # Configs written before saturation_flow existed keep the original value.
        self.saturation_flow = float(t.get("saturation_flow", 1800.0))

        # Storage limit per approach. Absent means unlimited, as before — queues
        # grow without bound instead of spilling back.
        capacity = t.get("queue_capacity")
        self.capacity: Optional[int] = None if capacity is None else int(capacity)
        if self.capacity is not None and self.capacity <= 0:
            raise ValueError("queue_capacity must be a positive number of vehicles")

        self.turning = TurningMix(config.get("turning"), seed)

        self.approaches: Dict[str, ApproachQueue] = {
            name: ApproachQueue(
                name, self.saturation_flow, self.capacity, self.turning.factors
            )
            for name in ("north", "south", "east", "west")
        }
        self.departed_vehicles: List[Vehicle] = []

    def arrive(self, arrivals: Dict[str, int], t: float) -> Dict[str, int]:
        """Queue arrivals; returns per-approach counts refused for lack of storage."""
        blocked: Dict[str, int] = {}
        for approach, n in arrivals.items():
            if approach in self.approaches:
                # Movements are drawn for every arrival, blocked or not, so the
                # movement stream does not depend on how full the approach is.
                movements = self.turning.sample(n)
                blocked[approach] = self.approaches[approach].arrive(n, t, movements)
        return blocked

    def arrive_emergency(self, approaches: Sequence[str], t: float) -> List[Vehicle]:
        """Queue one emergency vehicle at the head of each named approach."""
        return [
            self.approaches[a].arrive_emergency(t)
            for a in approaches
            if a in self.approaches
        ]

    def emergency_approaches(self) -> Set[str]:
        """Approaches with at least one emergency vehicle still waiting."""
        return {name for name, q in self.approaches.items() if q.has_emergency}

    def emergency_phases(self) -> Set[str]:
        """Phases that would serve a waiting emergency vehicle."""
        return {APPROACH_PHASE[a] for a in self.emergency_approaches()}

    def depart_phase(self, phase: str, dt: float, t: float) -> List[Vehicle]:
        """Depart from both approaches of the phase simultaneously."""
        if phase == "NS":
            pair = ("north", "south")
        else:
            pair = ("east", "west")
        departed = []
        for name in pair:
            departed.extend(self.approaches[name].depart(dt, t))
        self.departed_vehicles.extend(departed)
        return departed

    def queue_lengths(self) -> Dict[str, int]:
        return {name: q.length for name, q in self.approaches.items()}

    def clearance_time(self, phase: str) -> float:
        """
        startup_lost_time + max(approach_a, approach_b) * headway.
        Uses max (not sum) because both approaches clear simultaneously.
        """
        if phase == "NS":
            q = max(self.approaches["north"].length, self.approaches["south"].length)
        else:
            q = max(self.approaches["east"].length, self.approaches["west"].length)
        return self.startup_lost + q * self.headway

    def total_waiting(self) -> int:
        return sum(q.length for q in self.approaches.values())

    @property
    def total_blocked(self) -> int:
        return sum(q.blocked for q in self.approaches.values())
