"""Redis 키 상수 (flat naming — sensor_exporter.py 호환)."""

# 센서 (control_board가 SET, sensor_exporter가 read)
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

# Tach RPM (신규)
PUMP_RPM = 'pump_rpm'

def fan_rpm(idx):
    return f'fan_rpm_{idx}'

# 알람 (control_board가 SET/DEL)
def alarm(name):
    return 'alarm_' + name

# 통신 상태 (control_board 자체 카운트)
COMM_STATUS               = 'comm_status'
COMM_CONSECUTIVE_FAILURES = 'comm_consecutive_failures'
COMM_LAST_ERROR           = 'comm_last_error'
