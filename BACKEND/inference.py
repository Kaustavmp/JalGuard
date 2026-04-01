import json
import os
import re
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ENV_URL = os.getenv("ENV_URL", "http://127.0.0.1:7860").rstrip("/")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:11434/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "llama3.1:8b")
HF_TOKEN = os.getenv("HF_TOKEN", "ollama")
MIN_TASKS = int(os.getenv("MIN_TASKS", "3"))
RUN_ALL_TASKS = os.getenv("RUN_ALL_TASKS", "0") == "1"
STEP_LIMIT = 30 * 24

client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL, timeout=8.0, max_retries=0)


def emit(tag: str, payload: Dict[str, Any]) -> None:
    print(f"[{tag}] {json.dumps(payload, ensure_ascii=False)}", flush=True)


def parse_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def heuristic_action(obs: Dict[str, Any], step: int) -> Dict[str, Any]:
    tank = obs.get("tank_level", 0.0)
    demand = obs.get("forecasted_demand", 0.0)
    chlorine = obs.get("chlorine_level", 0.0)
    return {
        "pump_on": bool(obs.get("municipal_supply_active") and obs.get("power_active") and tank < max(900.0, demand * 8.0)),
        "release_water": 8.0 if tank > 1850 else 0.0,
        "chlorinate": bool(obs.get("bacteria_detected") and chlorine < 2.5),
        "check_leak": bool(step % 24 == 0),
        "harvester_on": bool(obs.get("is_raining") and tank < 1900),
    }


def llm_seed_action(task_id: str, obs: Dict[str, Any]) -> Dict[str, Any]:
    prompt = {
        "task_id": task_id,
        "observation": obs,
        "instruction": "Return only JSON action.",
    }
    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You control household water. Return only JSON with keys pump_on, release_water, "
                    "chlorinate, check_leak, harvester_on."
                ),
            },
            {"role": "user", "content": json.dumps(prompt)},
        ],
    )
    payload = parse_json(response.choices[0].message.content or "{}")
    for key in ["pump_on", "release_water", "chlorinate", "check_leak", "harvester_on"]:
        payload.setdefault(key, heuristic_action(obs, 0)[key])
    return {
        "pump_on": bool(payload["pump_on"]),
        "release_water": float(max(0.0, min(100.0, payload["release_water"]))),
        "chlorinate": bool(payload["chlorinate"]),
        "check_leak": bool(payload["check_leak"]),
        "harvester_on": bool(payload["harvester_on"]),
    }


def fetch_task_ids() -> List[str]:
    response = requests.get(f"{ENV_URL}/tasks", timeout=20)
    response.raise_for_status()
    tasks = response.json().get("tasks", [])
    ids = [task["id"] for task in tasks if "id" in task]
    if not ids:
        return ["easy_fill", "manage_demand", "odisha_survival"]
    if RUN_ALL_TASKS:
        return ids
    return ids[: max(3, MIN_TASKS)]


def run_episode(task_id: str) -> Dict[str, Any]:
    reset = requests.post(f"{ENV_URL}/reset", params={"task_id": task_id}, timeout=20)
    reset.raise_for_status()
    observation = reset.json()["observation"]

    emit("START", {"task_id": task_id, "model_name": MODEL_NAME, "api_base_url": API_BASE_URL})

    total_reward = 0.0
    done = False
    step = 0
    llm_action = None

    while not done and step < STEP_LIMIT:
        if step == 0:
            try:
                llm_action = llm_seed_action(task_id, observation)
            except Exception as err:
                llm_action = heuristic_action(observation, step)

        action = llm_action if step == 0 else heuristic_action(observation, step)

        stepped = requests.post(f"{ENV_URL}/step", json=action, timeout=20)
        stepped.raise_for_status()
        payload = stepped.json()
        observation = payload["observation"]
        reward = float(payload["reward"])
        done = bool(payload["done"])
        total_reward += reward

        emit("STEP", {"task_id": task_id, "step": step, "action": action, "reward": round(reward, 4), "done": done})
        step += 1

    grade = requests.post(f"{ENV_URL}/grader", json={"task_id": task_id}, timeout=20)
    grade.raise_for_status()
    score = float(grade.json().get("score", 0.0))

    result = {"task_id": task_id, "score": round(score, 4), "total_reward": round(total_reward, 4), "steps": step}
    emit("END", result)
    return result


def main() -> None:
    task_ids = fetch_task_ids()
    results = []
    for task_id in task_ids:
        results.append(run_episode(task_id))
    print(json.dumps({"summary": results}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
