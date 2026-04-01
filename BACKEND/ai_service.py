import json
import os
import re
from typing import Any, Dict, Optional, Tuple

from openai import OpenAI

try:
    from .models import Action, Observation
except ImportError:
    from models import Action, Observation


SYSTEM_PROMPT = """
You are JalGuard's policy planner for rural household water management in Odisha.
Return only JSON with keys:
{
  "pump_on": bool,
  "release_water": float (0-100),
  "chlorinate": bool,
  "check_leak": bool,
  "harvester_on": bool,
  "reasoning": string
}
Policy goals:
1) Always satisfy household demand.
2) Avoid overflow and avoid running dry.
3) Use chlorination only when bacteria risk exists and chlorine is not already high.
4) Check leaks periodically if suspicious.
5) Harvest rainwater when useful.
"""


def heuristic_action(obs: Observation) -> Action:
    must_fill = obs.tank_level < max(900.0, obs.forecasted_demand * 8.0)
    cautious_chlorination = obs.bacteria_detected and obs.chlorine_level < 2.5
    return Action(
        pump_on=bool(obs.municipal_supply_active and obs.power_active and must_fill),
        release_water=5.0 if obs.tank_level > 1800.0 else 0.0,
        chlorinate=bool(cautious_chlorination),
        check_leak=bool(obs.step_of_episode % 24 == 0),
        harvester_on=bool(obs.is_raining and obs.tank_level < 1900.0),
    )


class OllamaActionService:
    def __init__(self) -> None:
        base_url = os.getenv("OLLAMA_BASE_URL", os.getenv("API_BASE_URL", "http://localhost:11434/v1"))
        self.model = os.getenv("OLLAMA_MODEL", os.getenv("MODEL_NAME", "llama3.1:8b"))
        api_key = os.getenv("OLLAMA_API_KEY", os.getenv("HF_TOKEN", "ollama"))
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=4.0, max_retries=0)

    @staticmethod
    def _extract_json(payload: str) -> Dict[str, Any]:
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", payload, flags=re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))

    def suggest(self, observation: Observation, task_id: str, note: Optional[str] = None) -> Tuple[Action, str, Optional[str]]:
        user_prompt = {
            "task_id": task_id,
            "observation": observation.model_dump(),
            "note": note or "",
        }
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT.strip()},
                    {"role": "user", "content": json.dumps(user_prompt)},
                ],
            )
            content = response.choices[0].message.content or "{}"
            payload = self._extract_json(content)
            reasoning = payload.pop("reasoning", None)
            action = Action.model_validate(payload)
            return action, "ollama", reasoning
        except Exception:
            fallback = heuristic_action(observation)
            return fallback, "fallback", "Ollama unavailable, heuristic fallback applied."
