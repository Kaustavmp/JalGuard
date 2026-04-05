from __future__ import annotations

import re
import uuid
from typing import Any, Dict, Optional, Tuple

from backend.services.scenario_loader import ScenarioLoader


class ScenarioChatService:
    def __init__(self, scenario_loader: ScenarioLoader):
        self.scenario_loader = scenario_loader
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def _default_draft(self) -> Dict[str, Any]:
        return {
            "name": "",
            "season": "summer",
            "rain_level": "moderate",
            "rain_window": "evening",
            "leak_level": "medium",
            "supply_reliability": 0.5,
            "contamination_probability": 0.12,
            "demand_level": "medium",
        }

    def _parse_name(self, text: str) -> Optional[str]:
        patterns = [
            r'(?:name|call|title)\s+(?:it\s+)?(?:as\s+)?["\']?([A-Za-z0-9 \-_]{3,64})["\']?',
            r'["\']([A-Za-z0-9 \-_]{3,64})["\']\s+scenario',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _parse_percent(self, text: str, keyword: str) -> Optional[float]:
        pattern = rf"(\d{{1,3}})\s*%\s*(?:{keyword})|(?:{keyword}).*?(\d{{1,3}})\s*%"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            return None
        for group in match.groups():
            if group is not None:
                value = max(0, min(100, int(group)))
                return value / 100.0
        return None

    def _apply_user_message(self, draft: Dict[str, Any], text: str, pending_question: Optional[str]) -> Optional[str]:
        lower = text.lower()

        requested_name = self._parse_name(text)
        if requested_name:
            draft["name"] = requested_name

        if "post-monsoon" in lower:
            draft["season"] = "post-monsoon"
        elif "monsoon" in lower:
            draft["season"] = "monsoon"
        elif "winter" in lower:
            draft["season"] = "winter"
        elif "summer" in lower:
            draft["season"] = "summer"

        if any(token in lower for token in ("evening", "nightfall", "sunset")):
            draft["rain_window"] = "evening"
        elif "morning" in lower:
            draft["rain_window"] = "morning"
        elif "night" in lower:
            draft["rain_window"] = "night"
        elif "afternoon" in lower:
            draft["rain_window"] = "afternoon"

        if any(token in lower for token in ("flood", "very heavy", "extreme", "torrential")):
            draft["rain_level"] = "extreme"
        elif "heavy" in lower:
            draft["rain_level"] = "high"
        elif any(token in lower for token in ("moderate", "medium")):
            draft["rain_level"] = "moderate"
        elif any(token in lower for token in ("light", "drizzle", "low")):
            draft["rain_level"] = "light"
        elif any(token in lower for token in ("dry", "no rain")):
            draft["rain_level"] = "low"

        if "leak" in lower:
            if any(token in lower for token in ("high", "severe", "major")):
                draft["leak_level"] = "high"
            elif any(token in lower for token in ("low", "minor")):
                draft["leak_level"] = "low"
            elif any(token in lower for token in ("medium", "moderate")):
                draft["leak_level"] = "medium"

        supply_percent = self._parse_percent(lower, "supply")
        if supply_percent is not None:
            draft["supply_reliability"] = supply_percent
        elif any(token in lower for token in ("unreliable supply", "intermittent supply")):
            draft["supply_reliability"] = 0.45
        elif any(token in lower for token in ("reliable supply", "steady supply")):
            draft["supply_reliability"] = 0.82
        elif any(token in lower for token in ("very low supply", "rare supply")):
            draft["supply_reliability"] = 0.3

        if "contamination" in lower or "quality" in lower:
            if any(token in lower for token in ("high", "risky", "flood", "dirty")):
                draft["contamination_probability"] = 0.24
            elif any(token in lower for token in ("low", "clean", "safe")):
                draft["contamination_probability"] = 0.08
            elif any(token in lower for token in ("medium", "moderate")):
                draft["contamination_probability"] = 0.14

        if "demand" in lower:
            if "high" in lower:
                draft["demand_level"] = "high"
            elif "low" in lower:
                draft["demand_level"] = "low"
            elif any(token in lower for token in ("medium", "moderate")):
                draft["demand_level"] = "medium"

        if pending_question == "contamination" and re.search(r"\b(yes|sure|okay|ok|increase|do it)\b", lower):
            draft["contamination_probability"] = min(0.3, draft["contamination_probability"] + 0.08)

        if draft["contamination_probability"] < 0.16 and draft["rain_level"] in {"high", "extreme"}:
            return "contamination"
        return None

    def _rain_window_hours(self, window: str) -> Tuple[int, int]:
        return {
            "morning": (5, 10),
            "afternoon": (12, 16),
            "evening": (18, 22),
            "night": (22, 24),
        }.get(window, (18, 22))

    def _weather_curve(self, rain_level: str, rain_window: str) -> list[float]:
        base = {
            "low": 0.08,
            "light": 0.15,
            "moderate": 0.28,
            "high": 0.45,
            "extreme": 0.65,
        }.get(rain_level, 0.28)
        peak = {
            "low": 0.2,
            "light": 0.32,
            "moderate": 0.5,
            "high": 0.72,
            "extreme": 0.9,
        }.get(rain_level, 0.5)
        start, end = self._rain_window_hours(rain_window)
        values = [base for _ in range(24)]
        for hour in range(start, end):
            values[hour] = peak
        return [round(v, 2) for v in values]

    def _demand_curve(self, demand_level: str) -> list[float]:
        base = {"low": 16.0, "medium": 24.0, "high": 32.0}.get(demand_level, 24.0)
        morning_peak = {"low": 45.0, "medium": 68.0, "high": 92.0}.get(demand_level, 68.0)
        evening_peak = {"low": 42.0, "medium": 64.0, "high": 88.0}.get(demand_level, 64.0)
        values = []
        for hour in range(24):
            value = base
            if 6 <= hour <= 9:
                value = morning_peak
            elif 18 <= hour <= 21:
                value = evening_peak
            values.append(round(value, 1))
        return values

    def _leak_probability(self, leak_level: str) -> float:
        return {"low": 0.01, "medium": 0.03, "high": 0.06}.get(leak_level, 0.03)

    def _default_name(self, draft: Dict[str, Any]) -> str:
        season = str(draft["season"]).replace("-", " ").title()
        window = str(draft["rain_window"]).title()
        leak = str(draft["leak_level"]).title()
        return f"{season} {window} {leak} Leak Plan"

    def _scenario_payload(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        leak_probability = self._leak_probability(str(draft["leak_level"]))
        name = draft["name"] or self._default_name(draft)
        summary = (
            f"{draft['season'].title()} setup with {draft['rain_level']} rainfall in the {draft['rain_window']}, "
            f"{draft['leak_level']} leaks, and ~{int(float(draft['supply_reliability']) * 100)}% municipal supply availability."
        )
        return {
            "name": name,
            "description": summary,
            "weather_curve": self._weather_curve(str(draft["rain_level"]), str(draft["rain_window"])),
            "demand_curve": self._demand_curve(str(draft["demand_level"])),
            "leak_probability": leak_probability,
            "supply_reliability": round(float(draft["supply_reliability"]), 2),
            "contamination_probability": round(float(draft["contamination_probability"]), 2),
            "power_reliability": 0.9,
        }

    def _assistant_reply(self, draft: Dict[str, Any], ask_contamination: bool) -> str:
        leak_probability = self._leak_probability(str(draft["leak_level"]))
        start, end = self._rain_window_hours(str(draft["rain_window"]))
        rainfall_label = str(draft["rain_level"]).replace("high", "heavy")
        text = (
            f"I've set up a {draft['season']} village scenario with {rainfall_label} rainfall between "
            f"{start}:00 and {end}:00. Leak probability is about {int(leak_probability * 100)}% per step. "
            f"Municipal supply reliability is set to roughly {int(float(draft['supply_reliability']) * 100)}%."
        )
        if ask_contamination:
            return (
                f"{text} Given the rain conditions, I can raise contamination risk to make water quality management "
                f"more realistic. Want me to increase that?"
            )
        return (
            f"{text} I have saved this scenario to your history, so you can load it in one click anytime."
        )

    def process(self, message: str, session_id: Optional[str] = None, preferred_name: Optional[str] = None) -> Dict[str, Any]:
        sid = session_id or str(uuid.uuid4())
        session = self.sessions.setdefault(sid, {"draft": self._default_draft(), "pending_question": None})
        draft = session["draft"]
        if preferred_name:
            draft["name"] = preferred_name.strip()

        next_question = self._apply_user_message(draft, message, session.get("pending_question"))
        scenario = self._scenario_payload(draft)
        save_result = self.scenario_loader.save_chat_scenario(scenario=scenario, preferred_name=draft.get("name"))

        session["pending_question"] = next_question
        if save_result.get("saved"):
            draft["name"] = save_result.get("name", draft.get("name", ""))

        return {
            "session_id": sid,
            "reply": self._assistant_reply(draft, ask_contamination=next_question == "contamination"),
            "scenario": {
                "id": save_result.get("id"),
                "name": save_result.get("name"),
                "summary": save_result.get("summary", scenario.get("description", "")),
                "created_at": save_result.get("created_at"),
            },
        }
