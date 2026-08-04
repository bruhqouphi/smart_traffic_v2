from typing import Dict, List
import numpy as np


SCENARIOS: List[str] = ["balanced", "morning_rush", "evening_rush", "asymmetric"]


class TrafficGenerator:
    """Poisson arrival model. Rates in vehicles/second per approach."""

    def __init__(self, config: dict, scenario: str = "balanced", seed: int = 42):
        self.rng = np.random.default_rng(seed)
        scenario_cfg = config["scenarios"][scenario]
        self.rates: Dict[str, float] = dict(scenario_cfg)

        # Emergency vehicles are drawn from their own RNG stream so that turning
        # preemption on or off cannot perturb the ordinary arrival sequence —
        # without this, enabling EVs would silently change every baseline number.
        emergency = config.get("emergency") or {}
        self.emergency_enabled: bool = bool(emergency.get("enabled", False))
        self.emergency_rate: float = float(emergency.get("arrival_rate", 0.0))
        if self.emergency_rate < 0:
            raise ValueError("emergency.arrival_rate must not be negative")
        self._emergency_rng = np.random.default_rng(seed + 10_000)

    def arrivals(self, approach: str, dt: float) -> int:
        lam = self.rates.get(approach, 0.0) * dt
        return int(self.rng.poisson(lam))

    def arrivals_all(self, dt: float) -> Dict[str, int]:
        return {approach: self.arrivals(approach, dt) for approach in self.rates}

    def emergency_arrivals(self, dt: float) -> List[str]:
        """
        Approaches receiving an emergency vehicle this tick.

        Returns an empty list when preemption is disabled or the rate is 0, and
        draws nothing from the EV stream in that case. At most one EV per
        approach per tick — with dt=0.1 s and realistic rates the chance of two
        is negligible, and one keeps the arrival unambiguous.
        """
        if not self.emergency_enabled or self.emergency_rate <= 0.0:
            return []
        lam = self.emergency_rate * dt
        return [
            approach
            for approach in self.rates
            if self._emergency_rng.poisson(lam) > 0
        ]

    @property
    def approaches(self) -> List[str]:
        return list(self.rates.keys())
