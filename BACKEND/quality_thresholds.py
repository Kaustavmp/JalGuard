# quality_thresholds.py

# Based on JJM (Jal Jeevan Mission) standards
TDS_SAFE_LIMIT = 500.0               # mg/L, acceptable limit
TDS_HAZARDOUS_LIMIT = 2000.0         # mg/L

BACTERIA_SAFE_LIMIT = 0              # E.coli/100ml must be 0
BACTERIA_INITIAL_CHANCE = 0.05       # Baseline chance of contamination event
SUMMER_BACTERIA_MULTIPLIER = 2.0     # Summer heat increases bacteria risk

CHLORINE_EFFECTIVENESS = 0.95        # Fraction of bacteria killed per chlorination
CHLORINE_DOSE = 1.0                  # mg/L per action
MAX_CHLORINE_LEVEL = 4.0             # > 4.0 is irritating/harmful
CHLORINE_DECAY_RATE = 0.1            # mg/L decay per hour

# Penalty multipliers for bad water
CONTAMINATION_PENALTY = -5.0
NO_WATER_PENALTY = -10.0
