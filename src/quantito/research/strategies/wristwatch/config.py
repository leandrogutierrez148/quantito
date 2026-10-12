"""Frozen, hashable research assumptions."""

import hashlib
import json
import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Config:
    target: float = 0.15
    round_trip_cost_bps: float = 5.0
    execution_delay_minutes: int = 1
    gate_quantile: float = 0.8
    seed: int = 432
    hold_bars: int = 4
    max_iter: int = 100
    daily_delay_bars: int = 1

    def __post_init__(self):
        for name in ("target", "round_trip_cost_bps", "gate_quantile"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite")
        if not 0 < self.target <= 1 or self.round_trip_cost_bps < 0:
            raise ValueError("Invalid exposure or cost")
        if not 0 < self.gate_quantile < 1:
            raise ValueError("gate_quantile must be in (0, 1)")
        for name in ("execution_delay_minutes", "hold_bars", "max_iter", "daily_delay_bars"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("seed must be a nonnegative integer")

    @property
    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()
