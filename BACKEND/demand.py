# demand.py
import math
import random

def calculate_demand(hour: int, season: str) -> float:
    """Returns the expected true demand for the current hour."""
    # Real households have morning and evening peaks
    base = 15.0
    morning_peak = 60.0 * math.exp(-((hour - 8)**2) / 4.0)
    evening_peak = 50.0 * math.exp(-((hour - 19)**2) / 4.0)
    
    demand = base + morning_peak + evening_peak
    
    # Seasonality
    if season == "summer":
        demand *= 1.5
    elif season == "winter":
        demand *= 0.8
        
    # Introduce small random noise
    noise = random.uniform(0.9, 1.1)
    
    return max(5.0, demand * noise)

def forecast_demand(hour: int, season: str) -> float:
    """Returns the forecasted demand for the agent."""
    # Predict next hour without the exact noise factor
    next_hour = (hour + 1) % 24
    return calculate_demand(next_hour, season) / random.uniform(0.9, 1.1)  # Remove the exact random noise applied in reality
