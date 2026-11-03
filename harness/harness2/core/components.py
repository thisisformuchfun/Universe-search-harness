"""Bounded editable harness configuration. Scientific gates are not components."""

from dataclasses import dataclass, asdict
import math


@dataclass(frozen=True)
class HarnessBundle:
    mass_function_weight: float = 1.0
    precision_weight: float = 1.0
    efficiency_weight: float = 1.0

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != set(cls.__dataclass_fields__):
            raise ValueError("Proposal must contain exactly the three allowed numeric ranking weights")
        if any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 4
            for v in data.values()
        ):
            raise ValueError("Proposal weights must be finite numbers in [0,4]")
        if sum(data.values()) <= 0:
            raise ValueError("Zero ranking configuration rejected")
        return cls(**{k: float(v) for k, v in data.items()})

    def to_dict(self):
        return asdict(self)
