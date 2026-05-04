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

# 펌프 유량 추정 — 유량 센서 미장착이라 PWM duty + 토폴로지 multiplier 기반.
# 자세한 모델은 config.yaml의 pump 섹션 참고.
COOLANT_FLOW_LPM = 'coolant_flow_lpm'

# 팬 Tach RPM — 인덱스 0-based (gpu_temp_{i} 등 기존 컨벤션과 동일).
def fan_rpm(idx):
    return f'fan_rpm_{idx}'

# PWM duty readback (HR 0~11, 0~1000 = 0~100.0%)
# 인덱스 0-based, 채널 매핑은 wiring.pwm.{pump_ch,fan_ch} 기준.
def pwm_duty_pump(idx):
    return f'pwm_duty_pump_{idx}'

def pwm_duty_fan(idx):
    return f'pwm_duty_fan_{idx}'

# 통신 상태 (control_board 자체 카운트)
# 임계 알람은 Prometheus/Grafana 측에서 raw metric으로 평가하므로 별도 키 없음.
COMM_STATUS               = 'comm_status'
COMM_CONSECUTIVE_FAILURES = 'comm_consecutive_failures'
COMM_LAST_ERROR           = 'comm_last_error'
