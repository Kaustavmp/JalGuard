from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from . import (
    custom_user_scenario,
    drought_response,
    emergency_shortage_mgmt,
    festival_high_demand,
    monsoon_overflow,
    odisha_survival,
    tank_leakage_crisis,
)


@dataclass
class TaskProfile:
    id: str
    name: str
    description: str
    start_season: str
    demand_multiplier: float
    supply_reliability: float
    power_reliability: float
    leak_probability: float
    contamination_probability: float
    rain_probability: float
    season_shift: bool


def _build_profile(payload: Dict) -> TaskProfile:
    return TaskProfile(**payload)


def _alias(base: Dict, *, task_id: str, name: str, description: str, **overrides: float | bool | str) -> TaskProfile:
    payload = dict(base)
    payload.update({"id": task_id, "name": name, "description": description})
    payload.update(overrides)
    return _build_profile(payload)


_PUBLIC_TASKS: List[TaskProfile] = [
    _alias(
        odisha_survival.TASK,
        task_id="fill_timing",
        name="Fill Scheduling",
        description="Single source, no faults. Learn basic timing.",
        demand_multiplier=0.95,
        supply_reliability=0.88,
        power_reliability=0.96,
        leak_probability=0.0,
        contamination_probability=0.0,
        rain_probability=0.0,
        season_shift=False,
    ),
    _alias(
        festival_high_demand.TASK,
        task_id="multi_source",
        name="Multi-Source Selection",
        description="Borewell plus municipal with power cuts.",
        demand_multiplier=1.08,
        supply_reliability=0.56,
        power_reliability=0.78,
        leak_probability=0.01,
        contamination_probability=0.02,
        rain_probability=0.08,
        season_shift=False,
    ),
    _alias(
        odisha_survival.TASK,
        task_id="contamination",
        name="Contamination Triage",
        description="Quarantine and chlorinate decisions.",
        demand_multiplier=1.0,
        supply_reliability=0.52,
        power_reliability=0.86,
        leak_probability=0.01,
        contamination_probability=0.2,
        rain_probability=0.14,
        season_shift=False,
    ),
    _alias(
        drought_response.TASK,
        task_id="pump_health",
        name="Pump Health Management",
        description="Wear and repair timing.",
        demand_multiplier=1.05,
        supply_reliability=0.45,
        power_reliability=0.68,
        leak_probability=0.015,
        contamination_probability=0.05,
        rain_probability=0.06,
        season_shift=False,
    ),
    _alias(
        monsoon_overflow.TASK,
        task_id="monsoon",
        name="Monsoon Season",
        description="All hazards active with rain harvesting.",
    ),
    _alias(
        tank_leakage_crisis.TASK,
        task_id="leak_detection",
        name="Leak Detection",
        description="Hidden escalating fault under sensor noise.",
    ),
    _alias(
        emergency_shortage_mgmt.TASK,
        task_id="full_episode",
        name="30-Day Summer Survival",
        description="Everything active, designed to challenge frontier models.",
    ),
]

_INTERNAL_TASKS: List[TaskProfile] = [
    _build_profile(custom_user_scenario.TASK),
]

_TASKS: List[TaskProfile] = _PUBLIC_TASKS + _INTERNAL_TASKS

_TASK_MAP = {task.id: task for task in _TASKS}
_TASK_MAP.update(
    {
        "odisha_survival": _TASK_MAP["full_episode"],
        "drought_response": _TASK_MAP["pump_health"],
        "festival_high_demand": _TASK_MAP["multi_source"],
        "tank_leakage_crisis": _TASK_MAP["leak_detection"],
        "monsoon_overflow": _TASK_MAP["monsoon"],
        "emergency_shortage_mgmt": _TASK_MAP["full_episode"],
    }
)


def list_tasks() -> List[Dict[str, str]]:
    return [{"id": task.id, "name": task.name, "description": task.description} for task in _PUBLIC_TASKS]


def get_task(task_id: str) -> TaskProfile:
    return _TASK_MAP.get(task_id, _TASK_MAP["full_episode"])


def all_task_ids() -> List[str]:
    return [task.id for task in _PUBLIC_TASKS]
