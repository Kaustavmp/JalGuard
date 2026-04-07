from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Body, Request

from backend.core.actions import ConfigUpdateRequest, ConfigView, ValidationRunResponse, ValidationStatusResponse
from backend.core.config import AppConfig, load_runtime_config, save_runtime_config


router = APIRouter(tags=["admin"])
ROOT_DIR = Path(__file__).resolve().parents[2]


def _safe_config() -> Dict[str, Any]:
    config = AppConfig.from_env()
    return {
        "api_base_url": config.api_base_url,
        "model_name": config.model_name,
        "env_url": config.env_url,
        "auto_run_delay_ms": config.auto_run_delay_ms,
    }


@router.get("/api/admin/status")
def status(request: Request):
    env = request.app.state.env
    return {
        "fastapi": True,
        "environment": True,
        "assistant_active": True,
        "task_loaded": env.task.id,
        "step": env.current_step,
    }


@router.get("/api/admin/config", response_model=ConfigView)
def config_view():
    return ConfigView(**_safe_config())


@router.post("/api/admin/config", response_model=ConfigView)
def config_update(body: ConfigUpdateRequest):
    current = load_runtime_config()
    updates = body.model_dump(exclude_none=True)
    current.update(updates)
    save_runtime_config(current)
    return ConfigView(**_safe_config())


@router.post("/api/admin/playground")
def api_playground(request: Request, body: Dict[str, Any] = Body(...)):
    env = request.app.state.env
    route = body.get("route")
    payload = body.get("payload", {})

    if route == "/reset":
        task_id = payload.get("task_id", env.task.id)
        env.set_task(task_id)
        obs = env.reset()
        return {"ok": True, "response": {"observation": obs.model_dump()}}

    if route == "/state":
        return {"ok": True, "response": env.get_state()}

    if route == "/step":
        from backend.core.actions import Action

        action = Action.model_validate(payload)
        obs, reward, done, info = env.step(action)
        return {"ok": True, "response": {"observation": obs.model_dump(), "reward": reward, "done": done, "info": info}}

    return {"ok": False, "error": "Unsupported route"}


def _run_validation_job(job_id: str, jobs: Dict[str, Dict[str, str]]) -> None:
    jobs[job_id] = {"status": "running", "output": "Running pre_submission_check.py..."}
    env = os.environ.copy()
    env.setdefault("API_BASE_URL", "https://api.openai.com/v1")
    env.setdefault("MODEL_NAME", "gpt-4o-mini")
    if not env.get("OPENAI_API_KEY"):
        env["OPENAI_API_KEY"] = env.get("HF_TOKEN", "")

    process = subprocess.run(
        [sys.executable, "pre_submission_check.py"],
        cwd=str(ROOT_DIR),
        env=env,
        capture_output=True,
        text=True,
    )
    output = (process.stdout or "") + "\n" + (process.stderr or "")
    jobs[job_id] = {"status": "completed" if process.returncode == 0 else "failed", "output": output.strip()}


def _checklist_from_output(output: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("[") or "]" not in line:
            continue
        status = "pass" if line.startswith("[PASS]") else "fail" if line.startswith("[FAIL]") else "info"
        body = line.split("]", 1)[1].strip()
        if ":" in body:
            name, detail = body.split(":", 1)
            rows.append({"status": status, "name": name.strip(), "detail": detail.strip()})
        else:
            rows.append({"status": status, "name": body, "detail": ""})
    return rows


@router.post("/api/admin/run-validation", response_model=ValidationRunResponse)
def run_validation(request: Request, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs = request.app.state.validation_jobs
    jobs[job_id] = {"status": "queued", "output": "Queued"}
    background_tasks.add_task(_run_validation_job, job_id, jobs)
    return ValidationRunResponse(job_id=job_id, status="queued")


@router.get("/api/admin/validation/{job_id}", response_model=ValidationStatusResponse)
def validation_status(request: Request, job_id: str):
    jobs = request.app.state.validation_jobs
    data = jobs.get(job_id, {"status": "not_found", "output": "Job not found"})
    return ValidationStatusResponse(
        job_id=job_id,
        status=data["status"],
        output=data["output"],
        checklist=_checklist_from_output(data["output"]),
    )
