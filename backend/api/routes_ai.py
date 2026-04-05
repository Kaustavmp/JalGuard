from __future__ import annotations

from fastapi import APIRouter, Request

from backend.core.actions import AISuggestRequest, AISuggestResponse


router = APIRouter(tags=["ai"])


@router.post("/api/ai/suggest-action", response_model=AISuggestResponse)
def suggest_action(request: Request, body: AISuggestRequest):
    env = request.app.state.env
    ai = request.app.state.ai_service
    obs = body.observation or env._observation(leak_detected=False)
    task_id = body.task_id or env.task.id
    action, source, reasoning = ai.suggest(obs, task_id, body.note)
    return AISuggestResponse(action=action, source=source, reasoning=reasoning)
