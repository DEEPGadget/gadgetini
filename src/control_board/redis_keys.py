"""Redis key constants (flat naming - compatible with sensor_exporter.py)."""

# Sensors (control_board SETs, sensor_exporter reads)
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

# Pump flow estimation - no flow sensor installed, so derived from PWM duty + topology multiplier.
# See the pump section in config.yaml for the detailed model.
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

# Communication status (counted internally by control_board)
# No separate alarm keys - thresholds are evaluated as raw metrics on the Prometheus/Grafana side.
COMM_STATUS               = 'comm_status'
COMM_CONSECUTIVE_FAILURES = 'comm_consecutive_failures'
COMM_LAST_ERROR           = 'comm_last_error'
