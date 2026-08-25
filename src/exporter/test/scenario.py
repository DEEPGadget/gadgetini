"""Predefined test scenarios for control board simulation."""

# Scenario: NORMAL operation
SCENARIO_NORMAL = {
    "name": "Normal Operation",
    "coolant_inlet1": 37.0,
    "coolant_outlet1": 39.0,
    "coolant_inlet2": 36.5,
    "coolant_outlet2": 38.5,
    "coolant_flow_lpm": 3.5,
    "coolant_leak": 0,
    "coolant_level": 95,
    "air_temp": 22.0,
    "air_humidity": 45,
    "pump_duty": 60,
    "fan_rpm": [1800, 1800, 1750, 1750, 1700, 1700, 1800, 1750],
    "chassis_stability": 2,
    "pwm_curve_sources": [
        {"key": "coolant", "label": "Coolant Outlet Temp", "duty": 50},
        {"key": "chassis", "label": "Chassis Temperature", "duty": 45},
    ],
    "comm_status": "ok",
    "pcb_connected": True,
    "variation": {
        "coolant_temp_range": 0.5,
        "flow_range": 0.3,
        "air_temp_range": 0.3,
        "rpm_range": 100,
        "curve_duty_range": 3,
    }
}

# Scenario: WARNING - elevated temperature
SCENARIO_WARNING = {
    "name": "Warning - Elevated Temperature",
    "coolant_inlet1": 48.0,
    "coolant_outlet1": 51.0,
    "coolant_inlet2": 47.5,
    "coolant_outlet2": 50.5,
    "coolant_flow_lpm": 3.0,
    "coolant_leak": 0,
    "coolant_level": 90,
    "air_temp": 28.0,
    "air_humidity": 55,
    "pump_duty": 75,
    "fan_rpm": [3000, 3000, 2950, 2950, 3050, 3050, 3000, 2950],
    "chassis_stability": 2,
    "pwm_curve_sources": [
        {"key": "coolant", "label": "Coolant Outlet Temp", "duty": 75},
        {"key": "chassis", "label": "Chassis Temperature", "duty": 70},
    ],
    "comm_status": "ok",
    "pcb_connected": True,
    "variation": {
        "coolant_temp_range": 1.0,
        "flow_range": 0.4,
        "air_temp_range": 0.5,
        "rpm_range": 150,
        "curve_duty_range": 4,
    }
}

# Scenario: CRITICAL - very high temperature, potential leak
SCENARIO_CRITICAL = {
    "name": "Critical - Very High Temperature + Leak",
    "coolant_inlet1": 58.0,
    "coolant_outlet1": 62.0,
    "coolant_inlet2": 57.0,
    "coolant_outlet2": 61.0,
    "coolant_flow_lpm": 2.2,
    "coolant_leak": 1,
    "coolant_level": 75,
    "air_temp": 32.0,
    "air_humidity": 65,
    "pump_duty": 95,
    "fan_rpm": [4500, 4500, 4400, 4400, 4600, 4600, 4500, 4400],
    "chassis_stability": 5,
    "pwm_curve_sources": [
        {"key": "coolant", "label": "Coolant Outlet Temp", "duty": 100},
        {"key": "chassis", "label": "Chassis Temperature", "duty": 95},
    ],
    "comm_status": "ok",
    "pcb_connected": True,
    "variation": {
        "coolant_temp_range": 1.5,
        "flow_range": 0.5,
        "air_temp_range": 0.8,
        "rpm_range": 200,
        "curve_duty_range": 5,
    }
}

ALL_SCENARIOS = [SCENARIO_NORMAL, SCENARIO_WARNING, SCENARIO_CRITICAL]
