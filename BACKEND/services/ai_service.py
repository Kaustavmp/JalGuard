from __future__ import annotations

import json
import re
from typing import Optional, Tuple

from openai import OpenAI

from backend.core.actions import Action, Observation
from backend.core.config import AppConfig


class AIService:
    def __init__(self, config: AppConfig):
        self.config = config
        self.client = OpenAI(api_key=config.openai_api_key, base_url=config.api_base_url, timeout=5.0, max_retries=0)

    def heuristic_action(self, obs: Observation) -> Action:
        must_fill = obs.tank_level < max(900.0, obs.forecasted_demand * 8.0)
        return Action(
            pump_on=bool(obs.municipal_supply_active and obs.power_active and must_fill),
            release_water=6.0 if obs.tank_level > 1820 else 0.0,
            chlorinate=bool(obs.bacteria_detected and obs.chlorine_level < 2.3),
            check_leak=bool(obs.step_of_episode % 24 == 0),
            harvester_on=bool(obs.is_raining and obs.tank_level < 1900),
        )

    def _extract_json(self, raw: str) -> dict:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))

    def _narrative(self, observation: Observation, action: Action, raw_reasoning: Optional[str] = None) -> str:
        cleaned = (raw_reasoning or "").strip()
        if cleaned and len(cleaned) >= 40 and "{" not in cleaned and "}" not in cleaned:
            return cleaned

        tank_pct = max(0.0, min(100.0, (observation.tank_level / 2000.0) * 100.0))
        pump_text = "activate the pump now" if action.pump_on else "keep the pump off for this step"
        chlorine_text = "apply chlorination to stabilize quality" if action.chlorinate else "skip chlorination for now"
        release_text = f"release about {action.release_water:.0f}% to prevent overflow" if action.release_water > 0 else "hold current release to preserve storage"
        return (
            f"Tank is currently near {tank_pct:.0f}% capacity. I recommend you {pump_text}, {release_text}, "
            f"and {chlorine_text}. This should keep demand coverage stable while protecting water quality."
        )

    def suggest(self, observation: Observation, task_id: str, note: Optional[str]) -> Tuple[Action, str, str]:
        prompt = {
            "task_id": task_id,
            "observation": observation.model_dump(),
            "note": note or "",
        }
        try:
            response = self.client.chat.completions.create(
                model=self.config.model_name,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Return JSON with keys pump_on, release_water, chlorinate, check_leak, harvester_on, reasoning. "
                            "Reasoning must be plain English and actionable."
                        ),
                    },
                    {"role": "user", "content": json.dumps(prompt)},
                ],
            )
            payload = self._extract_json(response.choices[0].message.content or "{}")
            reasoning = str(payload.pop("reasoning", "AI recommendation generated."))
            action = Action.model_validate(payload)
            return action, "assistant", self._narrative(observation, action, reasoning)
        except Exception:
            action = self.heuristic_action(observation)
            return action, "assistant", self._narrative(observation, action)

    def health(self) -> bool:
        try:
            self.client.models.list()
            return True
        except Exception:
            return False
