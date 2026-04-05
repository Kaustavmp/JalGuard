from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


RUNTIME_CONFIG_PATH = Path(__file__).resolve().parents[1] / "data" / "runtime_config.json"


@dataclass
class AppConfig:
    api_base_url: str
    model_name: str
    openai_api_key: str
    env_url: str
    auto_run_delay_ms: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        runtime = load_runtime_config()
        return cls(
            api_base_url=runtime.get("api_base_url", os.getenv("API_BASE_URL", "https://api.openai.com/v1")),
            model_name=runtime.get("model_name", os.getenv("MODEL_NAME", "gpt-4o-mini")),
            openai_api_key=os.getenv("OPENAI_API_KEY", os.getenv("HF_TOKEN", "")),
            env_url=runtime.get("env_url", os.getenv("ENV_URL", "http://127.0.0.1:7860")),
            auto_run_delay_ms=int(runtime.get("auto_run_delay_ms", 250)),
        )


def load_runtime_config() -> Dict[str, str]:
    if not RUNTIME_CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(RUNTIME_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_runtime_config(payload: Dict[str, str]) -> None:
    RUNTIME_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
