from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Query, Request

from backend.core.actions import ScenarioSaveRequest


router = APIRouter(tags=["tasks"])


@router.get("/api/scenarios")
def list_scenarios(request: Request):
    return {"scenarios": request.app.state.scenario_loader.list()}


@router.post("/api/scenarios/validate")
def validate_scenario(request: Request, payload: dict = Body(...)):
    return request.app.state.scenario_loader.validate(payload)


@router.post("/api/scenarios/save")
def save_scenario(request: Request, body: ScenarioSaveRequest):
    return request.app.state.scenario_loader.save(body.scenario.model_dump())


@router.get("/api/scenarios/{scenario_id}")
def load_scenario(request: Request, scenario_id: str):
    try:
        scenario = request.app.state.scenario_loader.load(scenario_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"scenario": scenario}


@router.post("/api/scenarios/{scenario_id}/activate")
def activate_scenario(request: Request, scenario_id: str):
    env = request.app.state.env
    try:
        scenario = request.app.state.scenario_loader.load(scenario_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    env.load_custom_scenario(scenario, scenario_id=scenario_id)
    env.set_task("custom_user_scenario")
    return {"activated": True, "task_id": "custom_user_scenario", "scenario_id": scenario_id}


@router.get("/api/scenario-history")
def scenario_history(request: Request, q: str = Query(default="")):
    return {"history": request.app.state.scenario_loader.search_history(query=q)}


@router.post("/api/scenario-history/{scenario_id}/rename")
def rename_history_entry(request: Request, scenario_id: str, body: Dict[str, Any] = Body(...)):
    new_name = str(body.get("name", "")).strip()
    if len(new_name) < 2:
        raise HTTPException(status_code=400, detail="Scenario name is too short")
    try:
        return request.app.state.scenario_loader.rename(scenario_id, new_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/api/scenario-history/{scenario_id}")
def delete_history_entry(request: Request, scenario_id: str):
    return request.app.state.scenario_loader.delete(scenario_id)


@router.post("/api/scenario-history/{scenario_id}/load")
def load_history_entry(request: Request, scenario_id: str):
    env = request.app.state.env
    try:
        scenario = request.app.state.scenario_loader.load(scenario_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    env.load_custom_scenario(scenario, scenario_id=scenario_id)
    env.set_task("custom_user_scenario")
    return {"loaded": True, "scenario_id": scenario_id, "scenario": scenario}


@router.post("/api/scenario-chat/message")
def scenario_chat(request: Request, body: Dict[str, Any] = Body(...)):
    message = str(body.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="Please enter a scenario request")
    session_id = body.get("session_id")
    scenario_name = body.get("scenario_name")
    return request.app.state.scenario_chat_service.process(
        message=message,
        session_id=session_id,
        preferred_name=scenario_name,
    )
