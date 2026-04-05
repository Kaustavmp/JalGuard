from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Action(BaseModel):
    pump_on: bool = Field(False)
    release_water: float = Field(0.0, ge=0.0, le=100.0)
    chlorinate: bool = Field(False)
    check_leak: bool = Field(False)
    harvester_on: bool = Field(False)


class Observation(BaseModel):
    tank_level: float
    is_raining: bool
    municipal_supply_active: bool
    power_active: bool
    tds_reading: float
    bacteria_detected: bool
    forecasted_demand: float
    leak_detected: bool
    chlorine_level: float
    time_of_day: int = Field(..., ge=0, le=23)
    day_of_episode: int = Field(..., ge=0)
    step_of_episode: int = Field(..., ge=0)
    season: str
    cumulative_reward: float
    task_id: str


class ResetRequest(BaseModel):
    task_id: str = "fill_timing"


class GradeRequest(BaseModel):
    task_id: str = "fill_timing"


class StepResponse(BaseModel):
    observation: Observation
    reward: float
    done: bool
    info: Dict[str, Any]


class ResetResponse(BaseModel):
    observation: Observation
    info: Dict[str, Any]


class AISuggestRequest(BaseModel):
    task_id: Optional[str] = None
    observation: Optional[Observation] = None
    note: Optional[str] = None


class AISuggestResponse(BaseModel):
    action: Action
    source: str
    reasoning: str


class ScenarioConfig(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    weather_curve: List[float] = Field(..., min_length=24, max_length=24)
    demand_curve: List[float] = Field(..., min_length=24, max_length=24)
    leak_probability: float = Field(..., ge=0.0, le=1.0)
    description: Optional[str] = ""


class ScenarioSaveRequest(BaseModel):
    scenario: ScenarioConfig


class ConfigView(BaseModel):
    api_base_url: str
    model_name: str
    env_url: str
    auto_run_delay_ms: int


class ConfigUpdateRequest(BaseModel):
    api_base_url: Optional[str] = None
    model_name: Optional[str] = None
    env_url: Optional[str] = None
    auto_run_delay_ms: Optional[int] = Field(default=None, ge=50, le=5000)


class ValidationRunResponse(BaseModel):
    job_id: str
    status: str


class ValidationStatusResponse(BaseModel):
    job_id: str
    status: str
    output: str
    checklist: List[Dict[str, str]] = Field(default_factory=list)


class LogEntry(BaseModel):
    tag: str
    payload: Dict[str, Any]
