import random

# Fault probabilities
LEAK_DEVELOP_PROB = 0.01  # 1% chance per hour to develop a new leak
LEAK_SIZE_MIN = 5.0       # liters per hour
LEAK_SIZE_MAX = 50.0

def update_leaks(current_leak_rate):
    """Randomly develops or worsens leaks."""
    if random.random() < LEAK_DEVELOP_PROB:
        new_leak = random.uniform(LEAK_SIZE_MIN, LEAK_SIZE_MAX)
        return current_leak_rate + new_leak
    return current_leak_rate

def get_noisy_sensor_reading(true_val: float, sensor_type: str) -> float:
    """Simulates realistic low-cost sensor noise."""
    if sensor_type == "level":
        # +/- 5% error margin for ultrasonic level sensors
        error = true_val * random.uniform(-0.05, 0.05)
        return max(0.0, true_val + error)
        
    elif sensor_type == "tds":
        # +/- 10% error margin for cheap TDS probes
        error = true_val * random.uniform(-0.1, 0.1)
        return max(0.0, true_val + error)
        
    elif sensor_type == "chlorine":
        # +/- 15% error for chemical strips read digitally
        error = true_val * random.uniform(-0.15, 0.15)
        return max(0.0, true_val + error)
        
    return true_val

def get_noisy_boolean_sensor(true_val: float, sensor_type: str) -> bool:
    """Simulates a boolean sensor (like optical bacteria sensor) with false positives/negatives."""
    if sensor_type == "bacteria":
        # Bacteria is present if > 0
        has_bacteria = true_val > 0.0
        
        # 5% false positive, 5% false negative rates
        if has_bacteria and random.random() < 0.05:
            return False # False negative
        elif not has_bacteria and random.random() < 0.05:
            return True  # False positive
            
        return has_bacteria
        
    return bool(true_val)
