"""Redis key constants (flat naming, sensor_exporter.py compatible).

Written by data_crawler.py, read by sensor_exporter / display. Both backends
(PCB Modbus, legacy ADS1256) use the same key set.
"""

# Sensors
COOLANT_TEMP_INLET1  = 'coolant_temp_inlet1'
COOLANT_TEMP_INLET2  = 'coolant_temp_inlet2'
COOLANT_TEMP_OUTLET1 = 'coolant_temp_outlet1'
COOLANT_TEMP_OUTLET2 = 'coolant_temp_outlet2'
COOLANT_DELTA_T1     = 'coolant_delta_t1'
COOLANT_DELTA_T2     = 'coolant_delta_t2'
COOLANT_LEAK         = 'coolant_leak'
COOLANT_LEVEL        = 'coolant_level'
AIR_TEMP             = 'air_temp'
AIR_HUMIT            = 'air_humit'
CHASSIS_STABIL       = 'chassis_stabil'
HOST_STAT            = 'host_stat'

NTC_LOGICAL_TO_KEY = {
    'inlet1':  COOLANT_TEMP_INLET1,
    'outlet1': COOLANT_TEMP_OUTLET1,
    'inlet2':  COOLANT_TEMP_INLET2,
    'outlet2': COOLANT_TEMP_OUTLET2,
}

# Pump flow estimate (no flow sensor): from PWM duty + topology multiplier.
# See the pump section of pcb_config.yaml.
COOLANT_FLOW_LPM = 'coolant_flow_lpm'

# Fan Tach RPM - 0-based index (matches existing conventions like gpu_temp_{i}).
def fan_rpm(idx):
    return f'fan_rpm_{idx}'

# PWM duty readback (HR 0~11, 0~1000 = 0~100.0%)
# 0-based index; channel mapping comes from wiring.pwm.{pump_ch,fan_ch}.
def pwm_duty_pump(idx):
    return f'pwm_duty_pump_{idx}'

def pwm_duty_fan(idx):
    return f'pwm_duty_fan_{idx}'

# Manual PWM target (intended duty per channel, user-controlled in manual mode)
# 0-based index; same physical-channel convention as pwm_duty_*.
# Written by web UI (manual mode) or mode switch, read by data_crawler._apply_manual_pwm.
def manual_pwm_target_pump(idx):
    return f'manual_pwm_target_pump_{idx}'

def manual_pwm_target_fan(idx):
    return f'manual_pwm_target_fan_{idx}'

# Comm status (PCB path only — from health check / poll results).
COMM_STATUS               = 'comm_status'
COMM_CONSECUTIVE_FAILURES = 'comm_consecutive_failures'
COMM_LAST_ERROR           = 'comm_last_error'
