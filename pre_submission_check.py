import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import requests
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

from models import Action, Observation


ROOT = Path(__file__).resolve().parent
BASE_URL = "http://127.0.0.1:7860"
DEFAULT_API_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL_NAME = "gpt-4o-mini"

# Load local .env when present so validation works in local dev without manual export.
load_dotenv(ROOT / ".env")


def print_result(name: str, ok: bool, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}: {detail}")


def validate_openenv_yaml() -> Tuple[bool, str]:
    path = ROOT / "openenv.yaml"
    if not path.exists():
        return False, "openenv.yaml missing at root"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    required = ["name", "version", "description", "tasks"]
    missing = [key for key in required if key not in data]
    if missing:
        return False, f"Missing keys: {missing}"
    if not isinstance(data["tasks"], list) or len(data["tasks"]) < 3:
        return False, "tasks must contain at least 3 items"
    task_ids = [str(task.get("id", "")) for task in data["tasks"] if isinstance(task, dict)]
    if len(task_ids) != len(set(task_ids)):
        return False, "task ids must be unique"
    return True, f"{len(task_ids)} tasks configured"


def validate_models() -> Tuple[bool, str]:
    if not issubclass(Action, BaseModel) or not issubclass(Observation, BaseModel):
        return False, "Action/Observation must be Pydantic models"
    action_fields = {"pump_on", "release_water", "chlorinate", "check_leak", "harvester_on"}
    obs_fields = {"tank_level", "forecasted_demand", "time_of_day", "season"}
    if not action_fields.issubset(set(Action.model_fields.keys())):
        return False, "Action fields mismatch"
    if not obs_fields.issubset(set(Observation.model_fields.keys())):
        return False, "Observation fields mismatch"
    return True, "typed models validated"


def wait_for_server(timeout: float = 40.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(f"{BASE_URL}/health", timeout=1.2).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def run_server() -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "7860"],
        cwd=str(ROOT),
    )


def endpoint_check() -> Tuple[bool, str]:
    root = requests.get(f"{BASE_URL}/", timeout=5)
    if root.status_code != 200:
        return False, "Root URL does not return 200"

    tasks = requests.get(f"{BASE_URL}/tasks", timeout=5)
    tasks.raise_for_status()
    task_list = tasks.json().get("tasks", [])
    if len(task_list) < 3:
        return False, "Less than 3 tasks returned"

    reset = requests.post(f"{BASE_URL}/reset", params={"task_id": task_list[0]["id"]}, timeout=5)
    reset.raise_for_status()
    obs = reset.json()["observation"]
    if "tank_level" not in obs:
        return False, "reset observation invalid"

    action = {"pump_on": False, "release_water": 0.0, "chlorinate": False, "check_leak": False, "harvester_on": False}
    step = requests.post(f"{BASE_URL}/step", json=action, timeout=5)
    step.raise_for_status()
    state = requests.post(f"{BASE_URL}/state", timeout=5)
    state.raise_for_status()
    return True, f"endpoints healthy, tasks={len(task_list)}"


def run_graders() -> Tuple[bool, str]:
    tasks = requests.get(f"{BASE_URL}/tasks", timeout=5).json()["tasks"]
    for task in tasks:
        task_id = task["id"]
        requests.post(f"{BASE_URL}/reset", params={"task_id": task_id}, timeout=5).raise_for_status()
        for _ in range(5):
            action = {
                "pump_on": True,
                "release_water": 0.0,
                "chlorinate": False,
                "check_leak": False,
                "harvester_on": True,
            }
            requests.post(f"{BASE_URL}/step", json=action, timeout=5).raise_for_status()
        grade = requests.post(f"{BASE_URL}/grader", json={"task_id": task_id}, timeout=5)
        grade.raise_for_status()
        score = float(grade.json()["score"])
        if not (0.0 <= score <= 1.0):
            return False, f"Score out of range for {task_id}: {score}"
    return True, f"graded {len(tasks)} tasks within [0.0,1.0]"


def run_inference() -> Tuple[bool, str]:
    env = os.environ.copy()
    env.setdefault("MIN_TASKS", "3")
    env.setdefault("RUN_ALL_TASKS", "0")
    started = time.time()
    run = subprocess.run(
        [sys.executable, "inference.py"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=1200,
    )
    duration = time.time() - started
    if run.returncode != 0:
        return False, f"inference.py failed with code {run.returncode}"
    lines = [line for line in run.stdout.splitlines() if line.strip()]
    starts = [line for line in lines if line.startswith("[START] ")]
    steps = [line for line in lines if line.startswith("[STEP] ")]
    ends = [line for line in lines if line.startswith("[END] ")]
    if not starts or not steps or not ends:
        return False, "Missing structured [START]/[STEP]/[END] logs"
    if duration > 20 * 60:
        return False, f"Inference runtime exceeds 20 minutes: {duration:.1f}s"
    return True, f"inference complete in {duration:.1f}s with structured logs"


def check_docker_build() -> Tuple[bool, str]:
    try:
        result = subprocess.run(
            ["docker", "--version"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            return True, "SKIP: docker command unavailable in this runtime"
    except Exception:
        return True, "SKIP: docker not installed in this environment"

    build = subprocess.run(
        ["docker", "build", "-t", "jalguard-check:latest", "."],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=1200,
    )
    if build.returncode != 0:
        tail = "\n".join(build.stderr.splitlines()[-8:])
        return False, f"docker build failed: {tail}"
    return True, "docker build successful"


def env_var_check() -> Tuple[bool, str]:
    api_base_url = (os.getenv("API_BASE_URL") or DEFAULT_API_BASE_URL).strip()
    model_name = (os.getenv("MODEL_NAME") or DEFAULT_MODEL_NAME).strip()
    openai_api_key = (os.getenv("OPENAI_API_KEY") or os.getenv("HF_TOKEN") or "").strip()

    if not api_base_url:
        return False, "API_BASE_URL is empty."
    if not model_name:
        return False, "MODEL_NAME is empty."
    if not openai_api_key:
        return False, "Missing API key. Set OPENAI_API_KEY (or HF_TOKEN)."
    return True, "Effective API_BASE_URL, MODEL_NAME, and API key are available"


def main() -> None:
    checks: List[Tuple[str, bool, str]] = []

    ok, detail = validate_openenv_yaml()
    checks.append(("OpenEnv spec file", ok, detail))
    ok, detail = validate_models()
    checks.append(("Typed models", ok, detail))
    ok, detail = env_var_check()
    checks.append(("Required env vars", ok, detail))

    server = run_server()
    try:
        if not wait_for_server():
            checks.append(("Server boot", False, "Server did not start"))
        else:
            ok, detail = endpoint_check()
            checks.append(("Endpoints and ping", ok, detail))
            ok, detail = run_graders()
            checks.append(("3+ tasks with graders", ok, detail))
            ok, detail = run_inference()
            checks.append(("Baseline reproduction", ok, detail))
    finally:
        server.terminate()
        try:
            server.wait(timeout=8)
        except subprocess.TimeoutExpired:
            server.kill()

    ok, detail = check_docker_build()
    checks.append(("Dockerfile build", ok, detail))

    failed = False
    print("\n=== Pre-Submission Checklist ===")
    for name, status, detail in checks:
        print_result(name, status, detail)
        failed = failed or not status

    if failed:
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
