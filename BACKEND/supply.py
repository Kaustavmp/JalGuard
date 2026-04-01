# supply.py
import random

try:
    from .odisha_params import MUNICIPAL_SUPPLY_BASE_PROB, POWER_CUT_PROB, RAINFALL_PROBABILITIES, SUMMER_SUPPLY_PENALTY_PROB
except ImportError:
    from odisha_params import MUNICIPAL_SUPPLY_BASE_PROB, POWER_CUT_PROB, RAINFALL_PROBABILITIES, SUMMER_SUPPLY_PENALTY_PROB

def update_supply_conditions(season: str):
    """Updates raining, power cut, and municipal supply status."""
    
    # 1. Rain
    rain_prob = RAINFALL_PROBABILITIES.get(season, 0.05)
    is_raining = random.random() < rain_prob
    
    # 2. Power
    # Power cuts in rural Odisha are historically more common in summer
    power_penalty = 0.1 if season == "summer" else 0.0
    power_on = random.random() >= (POWER_CUT_PROB + power_penalty)
    
    # 3. Municipal Supply
    # Supply is very erratic, usually given in windows. We simulate a simple random block
    # but penalty during summer
    supply_prob = MUNICIPAL_SUPPLY_BASE_PROB
    if season == "summer":
        supply_prob -= SUMMER_SUPPLY_PENALTY_PROB
        
    supply_on = random.random() < max(0.05, supply_prob)
    
    return is_raining, power_on, supply_on
