from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class Action(BaseModel):
    pump_on: bool = Field(False, description="Turn on municipal supply pump if water and power are available.")
    release_water: float = Field(0.0, ge=0.0, le=100.0, description="Percentage of tank water to release/flush (0-100).")
    chlorinate: bool = Field(False, description="Add chlorine dose to the tank.")
    check_leak: bool = Field(False, description="Run active diagnostic to find leaks.")
    harvester_on: bool = Field(False, description="Enable rainwater harvesting if raining.")


class Observation(BaseModel):
    tank_level: float = Field(..., description="Current water level in liters (subject to sensor noise).")
    is_raining: bool = Field(..., description="Weather status.")
    municipal_supply_active: bool = Field(..., description="Is municipal water currently available in the pipe.")
    power_active: bool = Field(..., description="Is electricity currently available.")
    tds_reading: float = Field(..., description="TDS sensor reading (subject to noise).")
    bacteria_detected: bool = Field(..., description="Is contamination sensor triggered (boolean, noisy).")
    forecasted_demand: float = Field(..., description="Expected household demand in next step.")
    leak_detected: bool = Field(..., description="Result of check_leak action.")
    chlorine_level: float = Field(..., description="Current chlorine concentration.")
    time_of_day: int = Field(..., ge=0, le=23, description="Hour of day (0-23).")
    day_of_episode: int = Field(..., ge=0, description="Elapsed day index in the current episode.")
    step_of_episode: int = Field(..., ge=0, description="Elapsed step index in the current episode.")
    season: str = Field(..., description="Current season: summer, monsoon, winter.")
    cumulative_reward: float = Field(..., description="Cumulative reward collected in the current episode.")


class StepResponse(BaseModel):
    observation: Observation
    reward: float
    done: bool
    info: Dict[str, Any]


class ResetResponse(BaseModel):
    observation: Observation
    info: Dict[str, Any]


class ResetRequest(BaseModel):
    task_id: str = Field("odisha_survival", description="Task id to reset into.")


class GradeRequest(BaseModel):
    task_id: str = Field("odisha_survival", description="Task id for grading.")


class AISuggestRequest(BaseModel):
    observation: Optional[Observation] = Field(default=None, description="Optional observation override for inference.")
    task_id: str = Field("odisha_survival", description="Current task id for conditioning.")
    note: Optional[str] = Field(default=None, description="Optional user hint for the policy.")


class AISuggestResponse(BaseModel):
    action: Action
    source: str = Field(..., description="Whether action came from ollama or fallback heuristic.")
    reasoning: Optional[str] = Field(default=None, description="Short model explanation.")
