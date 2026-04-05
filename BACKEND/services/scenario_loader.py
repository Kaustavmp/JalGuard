from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.utils.validators import validate_scenario_payload


class ScenarioLoader:
    def __init__(self, scenario_dir: Path):
        self.scenario_dir = scenario_dir
        self.scenario_dir.mkdir(parents=True, exist_ok=True)
        self.history_path = self.scenario_dir / "_history.json"

    def validate(self, payload: Dict) -> Dict:
        result = validate_scenario_payload(payload)
        return {"valid": result.is_valid, "errors": result.errors}

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _normalize_id(self, name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
        return slug[:64] or "scenario"

    def _load_history(self) -> List[Dict[str, Any]]:
        if not self.history_path.exists():
            return []
        try:
            payload = json.loads(self.history_path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return payload
        except Exception:
            return []
        return []

    def _save_history(self, history: List[Dict[str, Any]]) -> None:
        self.history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")

    def _summary_for(self, scenario: Dict[str, Any]) -> str:
        if scenario.get("description"):
            return str(scenario["description"]).strip()[:200]

        leak = float(scenario.get("leak_probability", 0.03))
        rain_peak = max(float(x) for x in scenario.get("weather_curve", [0.2]))
        supply = float(scenario.get("supply_reliability", 0.5))

        if rain_peak >= 0.7:
            rain_note = "heavy rain"
        elif rain_peak >= 0.45:
            rain_note = "moderate rain"
        else:
            rain_note = "light rain"

        if leak >= 0.06:
            leak_note = "high leak risk"
        elif leak >= 0.03:
            leak_note = "medium leak risk"
        else:
            leak_note = "low leak risk"

        if supply <= 0.45:
            supply_note = "unreliable municipal supply"
        elif supply <= 0.7:
            supply_note = "mixed municipal supply"
        else:
            supply_note = "reliable municipal supply"

        return f"Simulates {rain_note}, {leak_note}, and {supply_note}."

    def _upsert_history(
        self,
        *,
        scenario_id: str,
        name: str,
        summary: str,
        source: str,
        task_id: Optional[str] = None,
        score: Optional[float] = None,
    ) -> Dict[str, Any]:
        history = self._load_history()
        now = self._now()
        existing = next((entry for entry in history if entry.get("id") == scenario_id), None)

        if existing:
            existing["name"] = name
            existing["summary"] = summary
            existing["updated_at"] = now
            existing["source"] = source or existing.get("source", "manual")
            if task_id is not None:
                existing["last_task_id"] = task_id
            if score is not None:
                existing["last_score"] = round(float(score), 4)
                existing["runs"] = int(existing.get("runs", 0)) + 1
            record = existing
        else:
            record = {
                "id": scenario_id,
                "name": name,
                "summary": summary,
                "created_at": now,
                "updated_at": now,
                "source": source,
                "last_task_id": task_id or "custom_user_scenario",
                "last_score": round(float(score), 4) if score is not None else None,
                "runs": 1 if score is not None else 0,
            }
            history.append(record)

        history.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        self._save_history(history)
        return record

    def save(self, scenario: Dict, *, scenario_id: Optional[str] = None, source: str = "manual") -> Dict:
        check = self.validate(scenario)
        if not check["valid"]:
            return {"saved": False, "errors": check["errors"]}

        name = str(scenario["name"]).strip()
        sid = scenario_id or self._normalize_id(name)
        path = self.scenario_dir / f"{sid}.json"
        path.write_text(json.dumps(scenario, indent=2), encoding="utf-8")

        record = self._upsert_history(
            scenario_id=sid,
            name=name,
            summary=self._summary_for(scenario),
            source=source,
        )
        return {"saved": True, "name": name, "id": sid, "summary": record["summary"], "created_at": record["created_at"]}

    def save_chat_scenario(
        self,
        *,
        scenario: Dict[str, Any],
        preferred_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        scenario = dict(scenario)
        if preferred_name:
            scenario["name"] = preferred_name.strip()
        if not scenario.get("name"):
            scenario["name"] = "Custom Village Plan"
        return self.save(scenario, source="chat")

    def list(self) -> List[Dict]:
        history = self._load_history()
        if history:
            return history

        items: List[Dict[str, Any]] = []
        for file in sorted(self.scenario_dir.glob("*.json")):
            if file.name.startswith("_"):
                continue
            try:
                payload = json.loads(file.read_text(encoding="utf-8"))
                items.append(
                    {
                        "id": file.stem,
                        "name": payload.get("name", file.stem),
                        "summary": self._summary_for(payload),
                        "created_at": self._now(),
                        "updated_at": self._now(),
                        "source": "legacy",
                        "last_task_id": "custom_user_scenario",
                        "last_score": None,
                        "runs": 0,
                    }
                )
            except Exception:
                continue
        if items:
            self._save_history(items)
        return items

    def load(self, scenario_id: str) -> Dict:
        path = self.scenario_dir / f"{scenario_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Scenario '{scenario_id}' not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def search_history(self, query: str = "") -> List[Dict[str, Any]]:
        query = query.strip().lower()
        rows = self.list()
        if not query:
            return rows
        return [item for item in rows if query in str(item.get("name", "")).lower()]

    def rename(self, scenario_id: str, new_name: str) -> Dict[str, Any]:
        scenario = self.load(scenario_id)
        scenario["name"] = new_name.strip()
        path = self.scenario_dir / f"{scenario_id}.json"
        path.write_text(json.dumps(scenario, indent=2), encoding="utf-8")

        record = self._upsert_history(
            scenario_id=scenario_id,
            name=scenario["name"],
            summary=self._summary_for(scenario),
            source="rename",
        )
        return {"renamed": True, "entry": record}

    def delete(self, scenario_id: str) -> Dict[str, Any]:
        path = self.scenario_dir / f"{scenario_id}.json"
        if path.exists():
            path.unlink()

        history = [item for item in self._load_history() if item.get("id") != scenario_id]
        self._save_history(history)
        return {"deleted": True, "id": scenario_id}

    def record_run(self, scenario_id: Optional[str], task_id: str, score: float) -> None:
        if not scenario_id:
            return
        try:
            scenario = self.load(scenario_id)
        except FileNotFoundError:
            return
        self._upsert_history(
            scenario_id=scenario_id,
            name=str(scenario.get("name", scenario_id)),
            summary=self._summary_for(scenario),
            source="run",
            task_id=task_id,
            score=score,
        )
