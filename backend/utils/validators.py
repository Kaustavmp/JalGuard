from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]


def validate_scenario_payload(payload: dict) -> ValidationResult:
    errors: List[str] = []

    weather = payload.get("weather_curve")
    demand = payload.get("demand_curve")
    leak_probability = payload.get("leak_probability")

    if not isinstance(weather, list) or len(weather) != 24:
        errors.append("weather_curve must have exactly 24 values.")
    if not isinstance(demand, list) or len(demand) != 24:
        errors.append("demand_curve must have exactly 24 values.")

    if isinstance(weather, list):
        for idx, value in enumerate(weather):
            if not isinstance(value, (int, float)) or value < 0 or value > 1:
                errors.append(f"weather_curve[{idx}] must be in range [0,1].")
                break

    if isinstance(demand, list):
        for idx, value in enumerate(demand):
            if not isinstance(value, (int, float)) or value <= 0:
                errors.append(f"demand_curve[{idx}] must be > 0.")
                break

    if not isinstance(leak_probability, (int, float)) or leak_probability < 0 or leak_probability > 1:
        errors.append("leak_probability must be in range [0,1].")

    return ValidationResult(is_valid=not errors, errors=errors)


def normalize_curve(values: List[float], default: float) -> List[float]:
    if not values or len(values) != 24:
        return [default for _ in range(24)]
    return [float(v) for v in values]
