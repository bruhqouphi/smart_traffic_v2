from typing import Dict, List
import numpy as np


SCENARIOS: List[str] = ["balanced", "morning_rush", "evening_rush", "asymmetric"]


class TrafficGenerator:
    """Poisson arrival model. Rates in vehicles/second per approach."""

    def __init__(self, config: dict, scenario: str = "balanced", seed: int = 42):
        self.rng = np.random.default_rng(seed)
        scenario_cfg = config["scenarios"][scenario]
        self.rates: Dict[str, float] = dict(scenario_cfg)

    def arrivals(self, approach: str, dt: float) -> int:
        lam = self.rates.get(approach, 0.0) * dt
        return int(self.rng.poisson(lam))

    def arrivals_all(self, dt: float) -> Dict[str, int]:
        return {approach: self.arrivals(approach, dt) for approach in self.rates}

    @property
    def approaches(self) -> List[str]:
        return list(self.rates.keys())
