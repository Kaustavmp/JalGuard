from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class EnvState:
    tank_level: float = 1000.0
    tds_actual: float = 320.0
    bacteria_actual: float = 0.0
    chlorine_actual: float = 0.6
    is_raining: bool = False
    supply_on: bool = False
    power_on: bool = True
    hour: int = 0
    day: int = 0
    season: str = "summer"
    leak_rate: float = 0.0
    current_demand: float = 0.0
    done: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
