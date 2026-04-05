from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Query, Request

from backend.core.actions import Action, GradeRequest, ResetRequest, ResetResponse, StepResponse
from backend.tasks.registry import list_tasks


router = APIRouter(tags=["environment"])


def _trajectory(request: Request) -> List[Dict[str, Any]]:
    return request.app.state.trajectory


@router.get("/tasks")
@router.get("/api/tasks")
def get_tasks():
    return {"tasks": list_tasks()}


@router.post("/reset", response_model=ResetResponse)
@router.post("/api/reset", response_model=ResetResponse)
@router.post("/reset()", response_model=ResetResponse)
def reset(
    request: Request,
    task_id: Optional[str] = Query(default=None),
    body: Optional[ResetRequest] = Body(default=None),
):
    env = request.app.state.env
    logger = request.app.state.logger
    selected = task_id or (body.task_id if body else "fill_timing")
    selected = env.set_task(selected)
    request.app.state.trajectory = []
    observation = env.reset()
    logger.start_episode(selected)
    return ResetResponse(observation=observation, info={"task_id": selected, "true_state": env.state.to_dict()})


@router.post("/step", response_model=StepResponse)
@router.post("/api/step", response_model=StepResponse)
@router.post("/step()", response_model=StepResponse)
def step(
    request: Request,
    action: Action,
    source: str = Query(default="human"),
    reasoning: Optional[str] = Query(default=None),
):
    env = request.app.state.env
    logger = request.app.state.logger
    observation, reward, done, info = env.step(action)

    _trajectory(request).append({"reward": reward, "action": action.model_dump(), "observation": observation.model_dump(), "done": done})
    logger.log_step(
        step=observation.step_of_episode,
        state=observation.model_dump(),
        action=action.model_dump(),
        reward=reward,
        source=source,
        reasoning=reasoning,
    )
    return StepResponse(observation=observation, reward=reward, done=done, info=info)


@router.get("/state")
@router.get("/api/state")
@router.post("/state")
@router.post("/api/state")
@router.post("/state()")
def state(request: Request):
    return request.app.state.env.get_state()


@router.post("/grader")
@router.post("/api/grader")
def grader(request: Request, body: Optional[GradeRequest] = Body(default=None)):
    env = request.app.state.env
    logger = request.app.state.logger
    scenario_loader = request.app.state.scenario_loader
    trajectory = _trajectory(request)
    task_id = body.task_id if body else env.task.id
    rewards = [float(item.get("reward", 0.0)) for item in trajectory]
    score = env.score_episode(rewards)
    logger.end_episode(final_score=score, steps=len(trajectory))
    scenario_loader.record_run(env.active_scenario_id, task_id, score)
    return {"task_id": task_id, "score": score, "steps": len(trajectory), "status": "graded"}


@router.get("/api/logs")
def logs(request: Request, limit: int = 200, mode: str = Query(default="all")):
    significant_only = mode.lower() == "significant"
    return {"logs": request.app.state.logger.get_recent_logs(limit=limit, significant_only=significant_only)}


@router.get("/api/episodes/current")
def current_episode(request: Request, prefer_latest: bool = Query(default=True)):
    logger = request.app.state.logger
    steps = logger.get_current_steps()
    if prefer_latest and not steps:
        latest = logger.latest_episode()
        steps = latest.get("steps", []) if latest else []
    return {"steps": steps}


@router.get("/api/episodes/summary")
def episode_summary(request: Request):
    return {"episodes": request.app.state.logger.summarize(), "latest": request.app.state.logger.latest_episode()}
