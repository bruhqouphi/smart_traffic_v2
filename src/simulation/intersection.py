from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Vehicle:
    vehicle_id: int
    approach: str
    arrival_time: float
    departure_time: Optional[float] = None

    @property
    def wait_time(self) -> Optional[float]:
        if self.departure_time is None:
            return None
        return self.departure_time - self.arrival_time


class ApproachQueue:
    def __init__(self, approach: str, saturation_flow: float = 1800.0):
        self.approach = approach
        # vehicles per second at saturation
        self._sat_flow_per_sec = saturation_flow / 3600.0
        self._queue: List[Vehicle] = []
        self._next_id = 0
        self._depart_accum: float = 0.0  # fractional accumulator for sub-step departures

    def arrive(self, n: int, t: float):
        for _ in range(n):
            self._queue.append(Vehicle(self._next_id, self.approach, t))
            self._next_id += 1

    def depart(self, dt: float, t: float) -> List[Vehicle]:
        self._depart_accum += self._sat_flow_per_sec * dt
        n = int(self._depart_accum)
        self._depart_accum -= n
        departed = []
        for _ in range(min(n, len(self._queue))):
            v = self._queue.pop(0)
            v.departure_time = t
            departed.append(v)
        return departed

    @property
    def length(self) -> int:
        return len(self._queue)


class Intersection:
    """
    Queue model for a 4-way intersection.
    NS phase serves north+south simultaneously; EW serves east+west.
    """

    def __init__(self, config: dict):
        t = config["timing"]
        self.startup_lost = float(t["startup_lost_time"])
        self.headway = float(t["headway"])

        self.approaches: Dict[str, ApproachQueue] = {
            "north": ApproachQueue("north"),
            "south": ApproachQueue("south"),
            "east": ApproachQueue("east"),
            "west": ApproachQueue("west"),
        }
        self.departed_vehicles: List[Vehicle] = []

    def arrive(self, arrivals: Dict[str, int], t: float):
        for approach, n in arrivals.items():
            if approach in self.approaches:
                self.approaches[approach].arrive(n, t)

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
