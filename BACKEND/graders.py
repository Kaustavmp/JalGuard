from typing import List, Dict, Any

# We use 7 graders indicating increasing difficulty
TASKS = [
    {
        "id": "easy_fill",
        "name": "Task 1: The Basics",
        "description": "Always-on power/supply. Just keep the tank full."
    },
    {
        "id": "manage_demand",
        "name": "Task 2: Morning Peaks",
        "description": "Satisfy highly variable domestic demand without overflowing."
    },
    {
        "id": "seasonal_shifts",
        "name": "Task 3: Turn of the Season",
        "description": "Survive shifting from winter (low demand) to summer (high demand)."
    },
    {
        "id": "chlorination",
        "name": "Task 4: The Outbreak",
        "description": "Severe bacteria event. Use chlorination safely, avoid overdosing."
    },
    {
        "id": "catch_leaks",
        "name": "Task 5: Old Pipes",
        "description": "Pipes slowly develop leaks. Run diagnostics and stop water loss."
    },
    {
        "id": "erratic_supply",
        "name": "Task 6: Odisha Realities",
        "description": "Municipal supply opens only for short random windows. Power cuts happen."
    },
    {
        "id": "odisha_survival",
        "name": "Task 7: Master Agent",
        "description": "All difficulty modifiers active. Fully stochastic environment. Survive 30 days."
    }
]

def score_episode(task_id: str, trajectory_info: List[Dict[str, Any]]) -> float:
    """Computes a normalized score [0.0, 1.0] from a trajectory."""
    
    # Calculate baseline max possible points (1 per step if demand met and no penalties)
    total_steps = len(trajectory_info)
    if total_steps == 0:
        return 0.0
        
    # The max positive score is roughly 1.0 * total_steps (no faults, always meet demand)
    max_possible_score = total_steps * 1.0
    
    # Calculate agent's true score (can be negative due to penalties)
    agent_raw_score = sum(step["reward"] for step in trajectory_info)
    
    # The minimum possible score is highly negative, let's bound it for normalization
    # -10 penalty per step for NO_WATER, -5 for contamination, etc.
    min_possible_score = -10.0 * total_steps
    
    if agent_raw_score >= max_possible_score:
        return 1.0
        
    # Normalize to 0-1
    normalized = (agent_raw_score - min_possible_score) / (max_possible_score - min_possible_score)
    return max(0.0, min(1.0, normalized))

def list_tasks() -> List[Dict[str, str]]:
    return TASKS
