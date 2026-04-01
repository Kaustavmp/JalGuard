# JalGuard Backend

This folder contains the complete OpenEnv-compatible backend for the JalGuard prototype.

## What is implemented

- Stateful FastAPI environment with typed `Action` and `Observation` models.
- OpenEnv endpoints:
  - `POST /reset`
  - `POST /step`
  - `GET|POST /state`
  - `POST /grader`
  - `GET /tasks`
- Task set with 7 graded scenarios from easy to full stochastic survival.
- Dashboard APIs:
  - `GET /dashboard` (web UI)
  - `POST /api/ai/suggest-action` (Ollama action suggestion)
- Baseline inference script using OpenAI client against Ollama-compatible endpoint.

## Ollama setup

Install and run Ollama locally, then pull your model:

```powershell
ollama pull llama3.1:8b
ollama serve
```

Environment variables:

- `API_BASE_URL` (default: `http://127.0.0.1:11434/v1`)
- `MODEL_NAME` (default: `llama3.1:8b`)
- `HF_TOKEN` (default: `ollama`)
- `ENV_URL` (default: `http://127.0.0.1:7860`)

## Local run

```powershell
pip install -r requirements.txt
uvicorn BACKEND.main:app --host 0.0.0.0 --port 7860
```

Then open:

- `http://127.0.0.1:7860/dashboard`

## Inference run

Run from repo root:

```powershell
python inference.py
```

Structured logs are emitted as:

- `[START] {...}`
- `[STEP] {...}`
- `[END] {...}`
