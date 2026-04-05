import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests
from openai import OpenAI


ENV_URL = os.getenv("ENV_URL", "http://127.0.0.1:7860").rstrip("/")
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", os.getenv("HF_TOKEN", ""))
TASK_LIMIT = int(os.getenv("MIN_TASKS", "3"))
STEP_CAP = int(os.getenv("INFERENCE_STEP_CAP", "240"))

client = OpenAI(api_key=OPENAI_API_KEY, base_url=API_BASE_URL, timeout=8.0, max_retries=0)


def emit(tag: str, payload: Dict[str, Any]) -> None:
    print(f"[{tag}] {json.dumps(payload, ensure_ascii=False)}", flush=True)


def parse_json(raw: str) -> Dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def fallback_action(state: Dict[str, Any], step: int) -> Dict[str, Any]:
    return {
        "pump_on": bool(state.get("municipal_supply_active") and state.get("power_active") and state.get("tank_level", 0) < 1400),
        "release_water": 6.0 if state.get("tank_level", 0) > 1850 else 0.0,
        "chlorinate": bool(state.get("bacteria_detected") and state.get("chlorine_level", 0) < 2.3),
        "check_leak": bool(step % 24 == 0),
        "harvester_on": bool(state.get("is_raining") and state.get("tank_level", 0) < 1900),
    }


def ask_ai(task: str, state: Dict[str, Any]) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "Return JSON with keys pump_on,release_water,chlorinate,check_leak,harvester_on.",
            },
            {"role": "user", "content": json.dumps({"task": task, "state": state})},
        ],
    )
    payload = parse_json(response.choices[0].message.content or "{}")
    action = fallback_action(state, 0)
    action.update(
        {
            "pump_on": bool(payload.get("pump_on", action["pump_on"])),
            "release_water": float(max(0.0, min(100.0, payload.get("release_water", action["release_water"])))),
            "chlorinate": bool(payload.get("chlorinate", action["chlorinate"])),
            "check_leak": bool(payload.get("check_leak", action["check_leak"])),
            "harvester_on": bool(payload.get("harvester_on", action["harvester_on"])),
        }
    )
    return action


def run_task(task_id: str) -> Dict[str, Any]:
    reset = requests.post(f"{ENV_URL}/reset", params={"task_id": task_id}, timeout=20)
    reset.raise_for_status()
    state = reset.json()["observation"]

    emit("START", {"task": task_id, "timestamp": datetime.now(timezone.utc).isoformat()})

    steps = 0
    done = False
    rewards: List[float] = []

    while not done and steps < STEP_CAP:
        try:
            action = ask_ai(task_id, state) if steps % 12 == 0 else fallback_action(state, steps)
            source = "assistant" if steps % 12 == 0 else "fallback"
        except Exception:
            action = fallback_action(state, steps)
            source = "fallback"

        response = requests.post(
            f"{ENV_URL}/step",
            params={"source": source},
            json=action,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        state = payload["observation"]
        reward = float(payload["reward"])
        done = bool(payload["done"])
        rewards.append(reward)

        emit("STEP", {"step": steps, "state": state, "action": action, "reward": round(reward, 4)})
        steps += 1

    grade = requests.post(f"{ENV_URL}/grader", json={"task_id": task_id}, timeout=20)
    grade.raise_for_status()
    final_score = float(grade.json().get("score", 0.0))
    emit("END", {"final_score": round(final_score, 4), "steps": steps})
    return {"task": task_id, "score": final_score, "steps": steps, "reward": round(sum(rewards), 4)}


def main() -> None:
    tasks_res = requests.get(f"{ENV_URL}/tasks", timeout=20)
    tasks_res.raise_for_status()
    tasks = [task["id"] for task in tasks_res.json().get("tasks", [])][: max(3, TASK_LIMIT)]
    summaries = [run_task(task_id) for task_id in tasks]
    print(json.dumps({"summary": summaries}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
