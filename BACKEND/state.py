# state.py
import dataclasses
from typing import Dict, Any

@dataclasses.dataclass
class EnvState:
    tank_level: float = 1000.0
    tds_actual: float = 300.0
    bacteria_actual: float = 0.0    # CFU/100ml
    chlorine_actual: float = 0.5    # mg/L
    is_raining: bool = False
    supply_on: bool = False
    power_on: bool = True
    hour: int = 0
    day: int = 0
    season: str = "summer"
    leak_rate: float = 0.0          # liters lost per hour
    current_demand: float = 0.0
    done: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)
