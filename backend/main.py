from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes_admin import router as admin_router
from backend.api.routes_ai import router as ai_router
from backend.api.routes_env import router as env_router
from backend.api.routes_tasks import router as tasks_router
from backend.core.config import AppConfig
from backend.core.environment import WaterEnvironment
from backend.services.ai_service import AIService
from backend.services.logger import EpisodeLogger
from backend.services.scenario_chat import ScenarioChatService
from backend.services.scenario_loader import ScenarioLoader
from backend.utils.exceptions import AppError


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="JalGuard OpenEnv Platform",
    description="Modular FastAPI backend for JalGuard with dashboard, scenario builder, analytics, and admin panel.",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

config = AppConfig.from_env()
app.state.config = config
app.state.env = WaterEnvironment()
app.state.logger = EpisodeLogger(BASE_DIR / "data" / "logs" / "episodes.jsonl")
app.state.scenario_loader = ScenarioLoader(BASE_DIR / "data" / "scenarios")
app.state.ai_service = AIService(config)
app.state.scenario_chat_service = ScenarioChatService(app.state.scenario_loader)
app.state.trajectory = []
app.state.validation_jobs = {}

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(env_router)
app.include_router(tasks_router)
app.include_router(ai_router)
app.include_router(admin_router)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


@app.exception_handler(Exception)
async def generic_error_handler(_: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Something went wrong. Try resetting the episode."},
    )


@app.on_event("startup")
def seed_demo_episode() -> None:
    env = app.state.env
    logger = app.state.logger
    ai_service = app.state.ai_service

    if logger.completed_episodes:
        return

    env.set_task("fill_timing")
    env.reset()
    logger.start_episode("fill_timing")
    rewards = []

    for _ in range(84):
        obs = env._observation(leak_detected=False)
        action = ai_service.heuristic_action(obs)
        observation, reward, done, _ = env.step(action)
        rewards.append(float(reward))
        logger.log_step(
            step=observation.step_of_episode,
            state=observation.model_dump(),
            action=action.model_dump(),
            reward=reward,
            source="assistant",
            reasoning="Automated warm-up run for analytics baseline.",
        )
        if done:
            break

    logger.end_episode(final_score=env.score_episode(rewards), steps=len(rewards))
    app.state.trajectory = []
    env.reset()


@app.get("/")
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/health")
def health() -> dict:
    env = app.state.env
    return {"status": "ok", "task_id": env.task.id, "step": env.current_step}


@app.get("/dashboard")
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/scenario-builder")
def scenario_builder() -> FileResponse:
    return FileResponse(STATIC_DIR / "scenario.html")


@app.get("/analytics")
def analytics() -> FileResponse:
    return FileResponse(STATIC_DIR / "analytics.html")


@app.get("/admin-panel")
def admin_panel() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin.html")


@app.get("/settings")
def settings_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "settings.html")


@app.get("/docs")
def docs_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "docs.html")
