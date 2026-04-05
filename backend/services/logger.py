from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class EpisodeLogger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.current: Dict[str, Any] = {}
        self.entries: List[Dict[str, Any]] = []
        self.completed_episodes: List[Dict[str, Any]] = []
        self.current_start_index = 0

    def _emit(self, tag: str, payload: Dict[str, Any]) -> None:
        line = f"[{tag}] {json.dumps(payload, ensure_ascii=False)}"
        self.entries.append(
            {
                "tag": tag,
                "payload": payload,
                "line": line,
                "human": self._human_line(tag, payload),
                "significant": self._is_significant(tag, payload),
            }
        )
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def _is_significant(self, tag: str, payload: Dict[str, Any]) -> bool:
        if tag in {"START", "END"}:
            return True
        if tag != "STEP":
            return False

        reward = abs(float(payload.get("reward", 0.0)))
        tank_before = float(payload.get("tank_before", payload.get("state", {}).get("tank_level", 0.0)))
        tank_after = float(payload.get("state", {}).get("tank_level", tank_before))
        tank_delta = abs(tank_after - tank_before)
        action = payload.get("action", {})
        state = payload.get("state", {})

        return bool(
            reward >= 1.4
            or tank_delta >= 140
            or action.get("chlorinate")
            or action.get("check_leak")
            or state.get("bacteria_detected")
            or state.get("leak_detected")
        )

    def _quality_status(self, state: Dict[str, Any]) -> str:
        if state.get("bacteria_detected") or float(state.get("tds_reading", 0.0)) > 1500:
            return "under watch"
        return "safe"

    def _human_line(self, tag: str, payload: Dict[str, Any]) -> str:
        if tag == "START":
            task = payload.get("task", "current task")
            return f"Episode started for {task.replace('_', ' ')}."

        if tag == "END":
            score = float(payload.get("final_score", 0.0))
            steps = int(payload.get("steps", 0))
            return f"Episode completed after {steps} steps. Final score: {score:.2f}."

        if tag != "STEP":
            return "System update received."

        step = int(payload.get("step", 0))
        reward = float(payload.get("reward", 0.0))
        action = payload.get("action", {})
        state = payload.get("state", {})

        action_bits = []
        action_bits.append("Pump activated" if action.get("pump_on") else "Pump idle")
        if float(action.get("release_water", 0.0)) > 0:
            action_bits.append(f"released {float(action.get('release_water', 0.0)):.0f}%")
        if action.get("chlorinate"):
            action_bits.append("chlorination applied")
        if action.get("harvester_on"):
            action_bits.append("rain harvesting enabled")
        if action.get("check_leak"):
            action_bits.append("leak inspection completed")

        tank_before = float(payload.get("tank_before", state.get("tank_level", 0.0)))
        tank_after = float(state.get("tank_level", tank_before))
        quality = self._quality_status(state)
        reward_text = f"{reward:+.2f}"

        return (
            f"Step {step} - {', '.join(action_bits)}. "
            f"Tank moved from {tank_before:.0f}L to {tank_after:.0f}L. "
            f"Water quality is {quality}. Reward earned: {reward_text}."
        )

    def start_episode(self, task_id: str) -> None:
        self.current_start_index = len(self.entries)
        self.current = {
            "task_id": task_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "steps": [],
            "total_reward": 0.0,
        }
        self._emit("START", {"task": task_id, "timestamp": self.current["started_at"]})

    def log_step(
        self,
        *,
        step: int,
        state: Dict[str, Any],
        action: Dict[str, Any],
        reward: float,
        source: str = "human",
        reasoning: Optional[str] = None,
    ) -> None:
        previous_state = (self.current.get("steps") or [{}])[-1].get("state", {})
        tank_before = float(previous_state.get("tank_level", state.get("tank_level", 0.0)))
        payload = {
            "step": step,
            "state": state,
            "action": action,
            "reward": round(float(reward), 4),
            "source": source,
            "tank_before": round(tank_before, 3),
        }
        if reasoning:
            payload["reasoning"] = reasoning
        self.current.setdefault("steps", []).append(payload)
        self.current["total_reward"] = self.current.get("total_reward", 0.0) + float(reward)
        self._emit("STEP", payload)

    def end_episode(self, final_score: float, steps: int) -> None:
        payload = {
            "final_score": round(float(final_score), 4),
            "steps": steps,
            "total_reward": round(float(self.current.get("total_reward", 0.0)), 4),
        }
        self.current["ended_at"] = datetime.now(timezone.utc).isoformat()
        self.current["final_score"] = payload["final_score"]
        self.completed_episodes.append(self.current)
        self._emit("END", payload)

    def get_recent_logs(self, limit: int = 300, significant_only: bool = False) -> List[str]:
        rows = self.entries[self.current_start_index :] if self.current_start_index < len(self.entries) else self.entries
        if significant_only:
            rows = [entry for entry in rows if entry.get("significant")]
        return [str(entry.get("human", "")) for entry in rows[-limit:] if entry.get("human")]

    def get_current_steps(self) -> List[Dict[str, Any]]:
        return self.current.get("steps", [])

    def latest_episode(self) -> Dict[str, Any]:
        if not self.completed_episodes:
            return {}
        return self.completed_episodes[-1]

    def summarize(self) -> List[Dict[str, Any]]:
        summaries = []
        for item in self.completed_episodes[-20:]:
            summaries.append(
                {
                    "task_id": item.get("task_id"),
                    "started_at": item.get("started_at"),
                    "ended_at": item.get("ended_at"),
                    "steps": len(item.get("steps", [])),
                    "final_score": item.get("final_score", 0.0),
                    "total_reward": round(float(item.get("total_reward", 0.0)), 4),
                }
            )
        return summaries
