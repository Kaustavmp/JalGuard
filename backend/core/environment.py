from __future__ import annotations

import math
import random
from typing import Any, Dict, Optional, Tuple

from backend.core.actions import Action, Observation
from backend.core.state import EnvState
from backend.tasks.registry import TaskProfile, get_task
from backend.utils.validators import normalize_curve


MAX_TANK_CAPACITY = 2000.0
MUNICIPAL_FILL_RATE = 380.0
RAIN_FILL_RATE = 150.0
NO_WATER_PENALTY = -10.0
CONTAMINATION_PENALTY = -5.0
TDS_HAZARD_LIMIT = 2000.0
MAX_CHLORINE_LEVEL = 4.0


class WaterEnvironment:
    def __init__(self) -> None:
        self.state = EnvState()
        self.task: TaskProfile = get_task("odisha_survival")
        self.custom_scenario: Optional[Dict[str, Any]] = None
        self.active_scenario_id: Optional[str] = None
        self.step_limit = 720
        self.current_step = 0
        self.score = 0.0

    def set_task(self, task_id: str) -> str:
        self.task = get_task(task_id)
        if task_id != "custom_user_scenario":
            self.custom_scenario = None
            self.active_scenario_id = None
        return self.task.id

    def load_custom_scenario(self, scenario: Dict[str, Any], scenario_id: Optional[str] = None) -> None:
        self.custom_scenario = scenario
        self.active_scenario_id = scenario_id

    def reset(self) -> Observation:
        self.state = EnvState()
        self.state.season = self.task.start_season
        self.current_step = 0
        self.score = 0.0
        return self._observation(leak_detected=False)

    def _season_for_day(self) -> str:
        if not self.task.season_shift:
            return self.state.season
        if self.state.day < 10:
            return "summer"
        if self.state.day < 20:
            return "monsoon"
        return "winter"

    def _weather_probability(self) -> float:
        if self.custom_scenario and self.task.id == "custom_user_scenario":
            return normalize_curve(self.custom_scenario.get("weather_curve", []), self.task.rain_probability)[self.state.hour]
        return self.task.rain_probability

    def _demand_value(self) -> float:
        if self.custom_scenario and self.task.id == "custom_user_scenario":
            curve = normalize_curve(self.custom_scenario.get("demand_curve", []), 30.0)
            return curve[self.state.hour]

        h = self.state.hour
        base = 16.0
        morning_peak = 58.0 * math.exp(-((h - 8) ** 2) / 4.0)
        evening_peak = 52.0 * math.exp(-((h - 19) ** 2) / 5.0)
        value = (base + morning_peak + evening_peak) * self.task.demand_multiplier
        return max(5.0, value * random.uniform(0.9, 1.1))

    def _leak_probability(self) -> float:
        if self.custom_scenario and self.task.id == "custom_user_scenario":
            return float(self.custom_scenario.get("leak_probability", self.task.leak_probability))
        return self.task.leak_probability

    def _supply_probability(self) -> float:
        if self.custom_scenario and self.task.id == "custom_user_scenario":
            return float(self.custom_scenario.get("supply_reliability", self.task.supply_reliability))
        return self.task.supply_reliability

    def _power_probability(self) -> float:
        if self.custom_scenario and self.task.id == "custom_user_scenario":
            return float(self.custom_scenario.get("power_reliability", self.task.power_reliability))
        return self.task.power_reliability

    def _contamination_probability(self) -> float:
        if self.custom_scenario and self.task.id == "custom_user_scenario":
            return float(self.custom_scenario.get("contamination_probability", self.task.contamination_probability))
        return self.task.contamination_probability

    def _source_quality(self, municipal: bool, rain: bool) -> Tuple[float, float]:
        if municipal:
            tds = random.uniform(220.0, 780.0)
            bacteria = random.uniform(10.0, 120.0) if random.random() < self._contamination_probability() else 0.0
            return tds, bacteria
        if rain:
            tds = random.uniform(15.0, 60.0)
            bacteria = random.uniform(5.0, 40.0) if random.random() < 0.12 else 0.0
            return tds, bacteria
        return 300.0, 0.0

    @staticmethod
    def _mix(v1: float, tds1: float, b1: float, v2: float, tds2: float, b2: float) -> Tuple[float, float, float]:
        total = v1 + v2
        if total <= 0:
            return 0.0, 0.0, 0.0
        return total, ((v1 * tds1) + (v2 * tds2)) / total, ((v1 * b1) + (v2 * b2)) / total

    def _observation(self, leak_detected: bool) -> Observation:
        return Observation(
            tank_level=max(0.0, self.state.tank_level * random.uniform(0.96, 1.04)),
            is_raining=self.state.is_raining,
            municipal_supply_active=self.state.supply_on,
            power_active=self.state.power_on,
            tds_reading=max(0.0, self.state.tds_actual * random.uniform(0.9, 1.1)),
            bacteria_detected=bool(self.state.bacteria_actual > 0 and random.random() > 0.04),
            forecasted_demand=self._demand_value() * random.uniform(0.95, 1.05),
            leak_detected=leak_detected,
            chlorine_level=max(0.0, self.state.chlorine_actual * random.uniform(0.86, 1.14)),
            time_of_day=self.state.hour,
            day_of_episode=self.state.day,
            step_of_episode=self.current_step,
            season=self.state.season,
            cumulative_reward=self.score,
            task_id=self.task.id,
        )

    def step(self, action: Action) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        reward = 0.0

        self.state.hour = (self.state.hour + 1) % 24
        if self.state.hour == 0:
            self.state.day += 1
        self.state.season = self._season_for_day()

        self.state.is_raining = random.random() < self._weather_probability()
        self.state.power_on = random.random() < self._power_probability()
        self.state.supply_on = random.random() < self._supply_probability()

        self.state.current_demand = self._demand_value()

        if random.random() < self._leak_probability():
            self.state.leak_rate += random.uniform(2.0, 22.0)

        inflow = 0.0
        inflow_tds = 0.0
        inflow_bac = 0.0

        if action.pump_on and self.state.supply_on and self.state.power_on:
            inflow += MUNICIPAL_FILL_RATE
            tds, bac = self._source_quality(municipal=True, rain=False)
            inflow_tds, inflow_bac = tds, bac
            reward -= 0.1

        if action.harvester_on and self.state.is_raining:
            tds, bac = self._source_quality(municipal=False, rain=True)
            if inflow > 0:
                total, mixed_tds, mixed_bac = self._mix(inflow, inflow_tds, inflow_bac, RAIN_FILL_RATE, tds, bac)
                inflow = total
                inflow_tds = mixed_tds
                inflow_bac = mixed_bac
            else:
                inflow = RAIN_FILL_RATE
                inflow_tds = tds
                inflow_bac = bac
            reward -= 0.05

        if inflow > 0:
            available = max(0.0, MAX_TANK_CAPACITY - self.state.tank_level)
            actual = min(available, inflow)
            if actual < inflow:
                reward -= 1.0
            _, self.state.tds_actual, self.state.bacteria_actual = self._mix(
                self.state.tank_level,
                self.state.tds_actual,
                self.state.bacteria_actual,
                actual,
                inflow_tds,
                inflow_bac,
            )
            self.state.tank_level += actual

        if action.chlorinate:
            self.state.chlorine_actual += 1.0
            self.state.bacteria_actual *= 0.1
            reward -= 0.35
        self.state.chlorine_actual = max(0.0, self.state.chlorine_actual - 0.1)

        if self.state.chlorine_actual > MAX_CHLORINE_LEVEL:
            reward -= 5.0

        flush = (action.release_water / 100.0) * self.state.tank_level
        self.state.tank_level -= flush
        if action.release_water > 0:
            reward -= 0.2

        leak_detected = False
        if action.check_leak:
            reward -= 0.2
            if self.state.leak_rate > 2.0:
                leak_detected = True
                self.state.leak_rate = 0.0
                reward += 0.8

        self.state.tank_level = max(0.0, self.state.tank_level - self.state.leak_rate)

        demand_met = min(self.state.tank_level, self.state.current_demand)
        self.state.tank_level -= demand_met

        demand_ratio = demand_met / self.state.current_demand if self.state.current_demand else 1.0
        reward += 1.0 if demand_ratio >= 1 else NO_WATER_PENALTY * (1 - demand_ratio)

        if self.state.bacteria_actual > 0:
            reward += CONTAMINATION_PENALTY * min(1.0, self.state.bacteria_actual / 100.0)
        if self.state.tds_actual > TDS_HAZARD_LIMIT:
            reward -= 2.0

        fill_ratio = self.state.tank_level / MAX_TANK_CAPACITY
        if 0.25 <= fill_ratio <= 0.8:
            reward += 0.2

        reward = max(-10.0, min(1.0, reward))
        self.score += reward
        self.current_step += 1
        self.state.done = self.current_step >= self.step_limit

        obs = self._observation(leak_detected=leak_detected)
        info = {
            "task_id": self.task.id,
            "fill_ratio": round(fill_ratio, 4),
            "unmet_demand": max(0.0, self.state.current_demand - demand_met),
            "true_state": self.state.to_dict(),
        }
        return obs, reward, self.state.done, info

    def score_episode(self, rewards: list[float]) -> float:
        steps = max(len(rewards), 1)
        max_score = steps * 1.0
        min_score = steps * -10.0
        raw = sum(rewards)
        norm = (raw - min_score) / (max_score - min_score)
        return max(0.0, min(1.0, norm))

    def get_state(self) -> Dict[str, Any]:
        return {
            "task_id": self.task.id,
            "step": self.current_step,
            "score": self.score,
            "state": self.state.to_dict(),
        }
