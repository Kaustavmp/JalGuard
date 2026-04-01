# JalGuard

JalGuard is a hackathon-ready rural water management simulator for Odisha with:

- OpenEnv-compliant backend APIs
- Interactive dashboard UI
- Ollama-powered action suggestions
- Root-level `inference.py` for baseline reproducibility
- Docker + `openenv.yaml` for deployment packaging

## Quick start (Windows)

1. Double-click `Start-JalGuard.bat`
2. Browser opens automatically at `http://127.0.0.1:7860/dashboard`

## Manual start

```powershell
pip install -r requirements.txt
uvicorn BACKEND.main:app --host 0.0.0.0 --port 7860
```

## Baseline inference

```powershell
python inference.py
```

## Pre-submission checklist run

```powershell
$env:API_BASE_URL="http://127.0.0.1:11434/v1"
$env:MODEL_NAME="llama3.1:8b"
$env:HF_TOKEN="ollama"
python pre_submission_check.py
```

## Important environment variables

- `API_BASE_URL` (Ollama OpenAI-compatible endpoint, default `http://127.0.0.1:11434/v1`)
- `MODEL_NAME` (default `llama3.1:8b`)
- `HF_TOKEN` (API key placeholder for OpenAI client; default `ollama`)
- `ENV_URL` (default `http://127.0.0.1:7860`)

## Deploy targets

- GitHub: `git@github.com:Kaustavmp/JalGuard.git`
- Hugging Face Space: `KaustavMP/JalGuard`
