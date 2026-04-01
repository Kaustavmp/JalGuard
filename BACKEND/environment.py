import random
from typing import Any, Dict, Tuple

try:
    from .demand import calculate_demand, forecast_demand
    from .faults import get_noisy_boolean_sensor, get_noisy_sensor_reading, update_leaks
    from .models import Action, Observation
    from .odisha_params import MAX_TANK_CAPACITY, MUNICIPAL_FILL_RATE, RAIN_FILL_RATE, STARTING_WATER_LEVEL
    from .quality import apply_chlorine, get_source_quality, mix_water
    from .quality_thresholds import (
        CONTAMINATION_PENALTY,
        MAX_CHLORINE_LEVEL,
        NO_WATER_PENALTY,
        TDS_HAZARDOUS_LIMIT,
        TDS_SAFE_LIMIT,
    )
    from .state import EnvState
    from .supply import update_supply_conditions
except ImportError:
    from demand import calculate_demand, forecast_demand
    from faults import get_noisy_boolean_sensor, get_noisy_sensor_reading, update_leaks
    from models import Action, Observation
    from odisha_params import MAX_TANK_CAPACITY, MUNICIPAL_FILL_RATE, RAIN_FILL_RATE, STARTING_WATER_LEVEL
    from quality import apply_chlorine, get_source_quality, mix_water
    from quality_thresholds import (
        CONTAMINATION_PENALTY,
        MAX_CHLORINE_LEVEL,
        NO_WATER_PENALTY,
        TDS_HAZARDOUS_LIMIT,
        TDS_SAFE_LIMIT,
    )
    from state import EnvState
    from supply import update_supply_conditions


TASK_PROFILES: Dict[str, Dict[str, Any]] = {
    "easy_fill": {
        "start_season": "winter",
        "force_supply": True,
        "force_power": True,
        "enable_leaks": False,
        "enable_contamination": False,
        "season_shifts": False,
        "demand_multiplier": 0.9,
    },
    "manage_demand": {
        "start_season": "summer",
        "force_supply": True,
        "force_power": True,
        "enable_leaks": False,
        "enable_contamination": False,
        "season_shifts": False,
        "demand_multiplier": 1.25,
    },
    "seasonal_shifts": {
        "start_season": "winter",
        "force_supply": True,
        "force_power": True,
        "enable_leaks": False,
        "enable_contamination": True,
        "season_shifts": True,
        "demand_multiplier": 1.0,
    },
    "chlorination": {
        "start_season": "summer",
        "force_supply": True,
        "force_power": True,
        "enable_leaks": False,
        "enable_contamination": True,
        "season_shifts": False,
        "demand_multiplier": 1.0,
    },
    "catch_leaks": {
        "start_season": "summer",
        "force_supply": True,
        "force_power": True,
        "enable_leaks": True,
        "enable_contamination": False,
        "season_shifts": False,
        "demand_multiplier": 1.0,
    },
    "erratic_supply": {
        "start_season": "summer",
        "force_supply": False,
        "force_power": False,
        "enable_leaks": True,
        "enable_contamination": True,
        "season_shifts": True,
        "demand_multiplier": 1.05,
    },
    "odisha_survival": {
        "start_season": "summer",
        "force_supply": False,
        "force_power": False,
        "enable_leaks": True,
        "enable_contamination": True,
        "season_shifts": True,
        "demand_multiplier": 1.15,
    },
}


class OdishaWaterEnv:
    def __init__(self) -> None:
        self.state = EnvState()
        self.task_id = "odisha_survival"
        self.step_limit = 30 * 24
        self.current_step = 0
        self.score = 0.0

    def set_task(self, task_id: str) -> str:
        self.task_id = task_id if task_id in TASK_PROFILES else "odisha_survival"
        return self.task_id

    def reset(self) -> Observation:
        profile = TASK_PROFILES[self.task_id]
        self.state = EnvState()
        self.state.tank_level = STARTING_WATER_LEVEL
        self.state.season = profile["start_season"]
        self.state.supply_on = bool(profile["force_supply"])
        self.state.power_on = bool(profile["force_power"])
        self.state.day = 0
        self.state.hour = 0
        self.state.leak_rate = 0.0

        if self.task_id in {"chlorination", "odisha_survival"}:
            self.state.bacteria_actual = random.uniform(10.0, 40.0)

        self.current_step = 0
        self.score = 0.0
        return self._get_observation()

    def step(self, action: Action) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        profile = TASK_PROFILES[self.task_id]
        reward = 0.0

        self._advance_time(profile)
        self._update_exogenous_state(profile)

        self.state.current_demand = max(5.0, calculate_demand(self.state.hour, self.state.season) * profile["demand_multiplier"])
        self._inject_faults(profile)

        incoming = []
        if action.pump_on and self.state.supply_on and self.state.power_on:
            tds, bac = get_source_quality(is_municipal=True, is_rain=False, season=self.state.season)
            incoming.append((MUNICIPAL_FILL_RATE, tds, bac))
            reward -= 0.1

        if action.harvester_on and self.state.is_raining:
            tds, bac = get_source_quality(is_municipal=False, is_rain=True, season=self.state.season)
            incoming.append((RAIN_FILL_RATE, tds, bac))
            reward -= 0.05

        if incoming:
            total_inflow = sum(volume for volume, _, _ in incoming)
            inflow_tds = sum(volume * tds for volume, tds, _ in incoming) / total_inflow
            inflow_bac = sum(volume * bac for volume, _, bac in incoming) / total_inflow

            available_space = max(0.0, MAX_TANK_CAPACITY - self.state.tank_level)
            actual_inflow = min(total_inflow, available_space)
            if total_inflow > available_space:
                reward -= 1.0

            _, self.state.tds_actual, self.state.bacteria_actual = mix_water(
                self.state.tank_level,
                self.state.tds_actual,
                self.state.bacteria_actual,
                actual_inflow,
                inflow_tds,
                inflow_bac,
            )
            self.state.tank_level += actual_inflow

        self.state.bacteria_actual, self.state.chlorine_actual = apply_chlorine(
            self.state.bacteria_actual,
            self.state.chlorine_actual,
            action.chlorinate,
        )
        if action.chlorinate:
            reward -= 0.35

        if self.state.chlorine_actual > MAX_CHLORINE_LEVEL:
            reward -= 5.0

        flush_amount = min(self.state.tank_level, (action.release_water / 100.0) * self.state.tank_level)
        self.state.tank_level -= flush_amount
        if action.release_water > 0.0:
            reward -= 0.2

        leak_loss = min(self.state.tank_level, self.state.leak_rate)
        self.state.tank_level = max(0.0, self.state.tank_level - leak_loss)

        demand_met = min(self.state.tank_level, self.state.current_demand)
        self.state.tank_level -= demand_met

        leak_detected = False
        if action.check_leak:
            reward -= 0.2
            if self.state.leak_rate > 2.0:
                leak_detected = True
                self.state.leak_rate = 0.0
                reward += 0.8

        demand_ratio = demand_met / self.state.current_demand if self.state.current_demand > 0 else 1.0
        if demand_ratio < 1.0:
            reward += NO_WATER_PENALTY * (1.0 - demand_ratio)
        else:
            reward += 1.0

        if self.state.bacteria_actual > 0.0:
            reward += CONTAMINATION_PENALTY * min(1.0, self.state.bacteria_actual / 100.0)
        if self.state.tds_actual > TDS_HAZARDOUS_LIMIT:
            reward -= 2.0
        elif self.state.tds_actual > TDS_SAFE_LIMIT:
            reward -= 0.5

        if self.state.leak_rate > 0:
            reward -= min(2.0, self.state.leak_rate / 20.0)

        fill_ratio = self.state.tank_level / MAX_TANK_CAPACITY
        if 0.25 <= fill_ratio <= 0.8:
            reward += 0.2

        reward = max(-10.0, min(1.0, reward))

        self.score += reward
        self.current_step += 1
        self.state.done = self.current_step >= self.step_limit

        obs = self._get_observation()
        obs.leak_detected = leak_detected

        info = {
            "task_id": self.task_id,
            "fill_ratio": round(fill_ratio, 4),
            "unmet_demand": max(0.0, self.state.current_demand - demand_met),
            "true_state": self.state.to_dict(),
        }
        return obs, reward, self.state.done, info

    def _advance_time(self, profile: Dict[str, Any]) -> None:
        self.state.hour = (self.state.hour + 1) % 24
        if self.state.hour == 0:
            self.state.day += 1

        if not profile["season_shifts"]:
            return

        if self.state.day < 10:
            self.state.season = "winter" if self.task_id == "seasonal_shifts" else "summer"
        elif self.state.day < 20:
            self.state.season = "summer"
        else:
            self.state.season = "monsoon"

    def _update_exogenous_state(self, profile: Dict[str, Any]) -> None:
        is_raining, power_on, supply_on = update_supply_conditions(self.state.season)
        self.state.is_raining = is_raining
        self.state.power_on = bool(profile["force_power"]) or power_on
        self.state.supply_on = bool(profile["force_supply"]) or supply_on

    def _inject_faults(self, profile: Dict[str, Any]) -> None:
        if profile["enable_leaks"]:
            self.state.leak_rate = update_leaks(self.state.leak_rate)

        if not profile["enable_contamination"]:
            return

        base_contam_prob = 0.03
        if self.state.season == "summer":
            base_contam_prob += 0.03
        if self.task_id == "chlorination":
            base_contam_prob += 0.14

        if random.random() < base_contam_prob:
            self.state.bacteria_actual += random.uniform(15.0, 120.0)

        if self.state.bacteria_actual > 0 and self.state.season == "summer":
            self.state.bacteria_actual *= 1.02

    def _get_observation(self) -> Observation:
        return Observation(
            tank_level=get_noisy_sensor_reading(self.state.tank_level, "level"),
            is_raining=self.state.is_raining,
            municipal_supply_active=self.state.supply_on,
            power_active=self.state.power_on,
            tds_reading=get_noisy_sensor_reading(self.state.tds_actual, "tds"),
            bacteria_detected=get_noisy_boolean_sensor(self.state.bacteria_actual, "bacteria"),
            forecasted_demand=forecast_demand(self.state.hour, self.state.season),
            leak_detected=False,
            chlorine_level=get_noisy_sensor_reading(self.state.chlorine_actual, "chlorine"),
            time_of_day=self.state.hour,
            day_of_episode=self.state.day,
            step_of_episode=self.current_step,
            season=self.state.season,
            cumulative_reward=self.score,
        )
