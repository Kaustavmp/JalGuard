# odisha_params.py

# Average precipitation probabilities per hour
RAINFALL_PROBABILITIES = {
    "summer": 0.02,   # Very rare
    "monsoon": 0.35,  # Frequent in Odisha
    "winter": 0.05
}

# Realities of rural Odisha municipal networks
MUNICIPAL_SUPPLY_BASE_PROB = 0.25      # Erratic
SUMMER_SUPPLY_PENALTY_PROB = 0.15      # Even worse in summer
POWER_CUT_PROB = 0.15                  # Grid unreliability

# Tank parameters
MAX_TANK_CAPACITY = 2000.0             # Liters
MUNICIPAL_FILL_RATE = 400.0            # Liters per hour
RAIN_FILL_RATE = 150.0                 # Liters per hour during rain

STARTING_WATER_LEVEL = 1000.0
