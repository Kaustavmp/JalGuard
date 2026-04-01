import random

try:
    from .quality_thresholds import (
        BACTERIA_INITIAL_CHANCE, SUMMER_BACTERIA_MULTIPLIER,
        CHLORINE_EFFECTIVENESS, CHLORINE_DECAY_RATE
    )
except ImportError:
    from quality_thresholds import (
        BACTERIA_INITIAL_CHANCE, SUMMER_BACTERIA_MULTIPLIER,
        CHLORINE_EFFECTIVENESS, CHLORINE_DECAY_RATE
    )

def get_source_quality(is_municipal: bool, is_rain: bool, season: str):
    """Returns (TDS, Bacteria_CFU) for the incoming water source."""
    
    tds = 0.0
    bacteria = 0.0
    
    if is_municipal:
        # Typical Odisha rural TDS ranges from 200 to 800
        tds = random.uniform(200.0, 800.0)
        
        # Risk of bacteria in pipes
        bac_chance = BACTERIA_INITIAL_CHANCE
        if season == "summer":
            bac_chance *= SUMMER_BACTERIA_MULTIPLIER
            
        if random.random() < bac_chance:
            bacteria = random.uniform(10.0, 150.0) # Contaminated plug
            
    elif is_rain:
        # Rainwater has low TDS but can wash roof debris
        tds = random.uniform(10.0, 50.0)
        if random.random() < 0.1: # 10% chance roof is dirty
            bacteria = random.uniform(5.0, 50.0)
            
    return tds, bacteria

def mix_water(v1, tds1, bac1, v2, tds2, bac2):
    """Mixes two volumes of water and returns new volume, TDS, Bacteria."""
    total_v = v1 + v2
    if total_v <= 0:
        return 0, 0, 0
    # Weighted average concentrations
    new_tds = ((v1 * tds1) + (v2 * tds2)) / total_v
    new_bac = ((v1 * bac1) + (v2 * bac2)) / total_v
    return total_v, new_tds, new_bac

def apply_chlorine(current_bacteria, current_chlorine_level, dose_active):
    """Reduces bacteria based on chlorine, decays chlorine."""
    # Active killing
    killed = 0.0
    if current_chlorine_level > 0.5:
        # Kills proportional to effectiveness + level
        killed = current_bacteria * CHLORINE_EFFECTIVENESS * min(1.0, current_chlorine_level)
    
    new_bac = max(0.0, current_bacteria - killed)
    
    # Add new dose if agent chose to
    new_chl = current_chlorine_level
    if dose_active:
        new_chl += 1.0 # 1 mg/L addition
        
    # Decay
    new_chl = max(0.0, new_chl - CHLORINE_DECAY_RATE)
    
    return new_bac, new_chl
