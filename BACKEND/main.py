from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

try:
    from .ai_service import OllamaActionService, heuristic_action
    from .environment import OdishaWaterEnv
    from .graders import list_tasks, score_episode
    from .models import (
        AISuggestRequest,
        AISuggestResponse,
        Action,
        GradeRequest,
        ResetRequest,
        ResetResponse,
        StepResponse,
    )
except ImportError:
    from ai_service import OllamaActionService, heuristic_action
    from environment import OdishaWaterEnv
    from graders import list_tasks, score_episode
    from models import (
        AISuggestRequest,
        AISuggestResponse,
        Action,
        GradeRequest,
        ResetRequest,
        ResetResponse,
        StepResponse,
    )

app = FastAPI(
    title="JalGuard Rural Water Simulator",
    description="OpenEnv-compatible Odisha household water management environment with dashboard + Ollama copilot.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

env = OdishaWaterEnv()
trajectory: List[Dict[str, Any]] = []
ai_service = OllamaActionService()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def read_root():
    return {"message": "JalGuard environment online", "dashboard": "/dashboard", "health": "/health"}


@app.get("/dashboard")
def dashboard():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Dashboard UI missing. Build static assets first."}


@app.get("/health")
def health():
    return {"status": "ok", "task_id": env.task_id, "step": env.current_step}


@app.get("/tasks")
@app.get("/api/tasks")
def get_tasks():
    return {"tasks": list_tasks()}


@app.post("/reset", response_model=ResetResponse)
@app.post("/api/reset", response_model=ResetResponse)
@app.post("/reset()")
def reset(
    task_id: Optional[str] = Query(default=None),
    body: Optional[ResetRequest] = Body(default=None),
):
    global trajectory
    selected_task = task_id or (body.task_id if body else "odisha_survival")
    selected_task = env.set_task(selected_task)
    trajectory = []
    obs = env.reset()
    return ResetResponse(
        observation=obs,
        info={"task_id": selected_task, "true_state": env.state.to_dict()},
    )


@app.post("/step", response_model=StepResponse)
@app.post("/api/step", response_model=StepResponse)
@app.post("/step()", response_model=StepResponse)
def step(action: Action):
    global trajectory
    obs, reward, done, info = env.step(action)
    trajectory.append(
        {
            "action": action.model_dump(),
            "observation": obs.model_dump(),
            "reward": reward,
            "done": done,
            "info": info,
        }
    )
    return StepResponse(observation=obs, reward=reward, done=done, info=info)


@app.get("/state")
@app.get("/api/state")
@app.post("/state")
@app.post("/api/state")
@app.post("/state()")
def get_state():
    return {"state": env.state.to_dict(), "step": env.current_step, "score": env.score, "task_id": env.task_id}


@app.post("/grader")
@app.post("/api/grader")
def grader(body: Optional[GradeRequest] = Body(default=None)):
    request = body or GradeRequest(task_id=env.task_id)
    score = score_episode(request.task_id, trajectory)
    return {"task_id": request.task_id, "score": score, "steps": len(trajectory), "status": "graded"}


@app.post("/api/ai/suggest-action", response_model=AISuggestResponse)
def suggest_action(request: AISuggestRequest):
    observation = request.observation or env._get_observation()
    action, source, reasoning = ai_service.suggest(observation, request.task_id or env.task_id, request.note)
    return AISuggestResponse(action=action, source=source, reasoning=reasoning)


@app.get("/baseline")
def run_baseline(task_id: str = "easy_fill"):
    local_env = OdishaWaterEnv()
    selected_task = local_env.set_task(task_id)
    obs = local_env.reset()
    trajectory_buffer: List[Dict[str, Any]] = []
    for _ in range(local_env.step_limit):
        action = heuristic_action(obs)
        obs, reward, done, info = local_env.step(action)
        trajectory_buffer.append({"reward": reward, "done": done, "info": info})
        if done:
            break

    score = score_episode(selected_task, trajectory_buffer)
    return {"task_id": selected_task, "baseline_score": score, "status": "completed", "steps": len(trajectory_buffer)}
