---
title: JalGuard
emoji: 💧
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: other
tags:
  - openenv
---

# JalGuard

JalGuard is an OpenEnv-compatible rural water intelligence platform with a modular FastAPI backend, conversational AI copilot, and a 4-page responsive UI plus user settings.

## Main UI Pages

1. Dashboard (Live Control Center)
2. Scenario Builder
3. Analytics & Reports
4. Admin Panel (Validation + Developer Tools)

## Backend Architecture

```
backend/
  core/
    environment.py
    actions.py
    state.py
    config.py
  tasks/
    *.py
    registry.py
  services/
    ai_service.py
    logger.py
    scenario_loader.py
  api/
    routes_env.py
    routes_tasks.py
    routes_ai.py
    routes_admin.py
  utils/
    validators.py
    exceptions.py
```

## Run

```powershell
pip install -r requirements.txt
python start_jalguard.py
```

or

```powershell
uvicorn backend.main:app --host 0.0.0.0 --port 7860
```

Open: `http://127.0.0.1:7860/dashboard`

## Inference

`inference.py` is at repo root and emits structured logs:

- `[START] {...}`
- `[STEP] {...}`
- `[END] {...}`

Run:

```powershell
python inference.py
```

## Required Environment Variables

- `API_BASE_URL` (default: `https://api.openai.com/v1`)
- `MODEL_NAME` (default: `gpt-4o-mini`)
- `OPENAI_API_KEY`

## Deployment Targets

- GitHub: `git@github.com:Kaustavmp/JalGuard.git`
- Hugging Face Space: `KaustavMP/JalGuard`
