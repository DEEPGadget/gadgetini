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

# Control mode: 'auto' = duty from the fan curve in pcb_config.yaml,
# 'manual' = duty from the manual_pwm_target_* keys below.
CONTROL_MODE = 'control_mode'

# Manual PWM target (intended duty per channel, user-controlled in manual mode)
# 0-based index; same physical-channel convention as pwm_duty_*.
# Written by web UI (manual mode) or mode switch, read by pcb_control.apply_manual_pwm.
def manual_pwm_target_pump(idx):
    return f'manual_pwm_target_pump_{idx}'

def manual_pwm_target_fan(idx):
    return f'manual_pwm_target_fan_{idx}'

# Fan curve multi-source (per-source duty and winning source key)
def pwm_curve_source_duty(key):
    return f'pwm_curve_duty_{key}'

PWM_CURVE_SELECTED_SOURCE = 'pwm_curve_selected_source'

# Comm status (PCB path only — from health check / poll results).
COMM_STATUS               = 'comm_status'
COMM_CONSECUTIVE_FAILURES = 'comm_consecutive_failures'
COMM_LAST_ERROR           = 'comm_last_error'   # last PCB failure reason, human-readable

# ── Liveness ───────────────────────────────────────────────────────────────
# Redis is the *current-value* bus shared by the exporter, the display and the
# web UI; history lives in Prometheus. Every sampled key is therefore written
# with a TTL (`ex=SAMPLE_TTL_SEC`) so it disappears by itself when its writer
# stops refreshing it. A crashed collector, an unplugged PCB, a dead sensor and
# a lost serial port then all look the same to every reader: "no key" — the
# exporter's exists() gates drop the metric instead of exporting a stale value.
#
# The only keys written WITHOUT a TTL are commands the web UI writes once and no
# loop refreshes: CONTROL_MODE and manual_pwm_target_*. They do not need to
# survive a restart either — data_crawler forces CONTROL_MODE back to 'auto' at
# boot and the UI re-seeds the targets on every switch to manual.
SAMPLE_TTL_SEC = 5          # default; data_crawler overrides from loop.cycle_seconds


def set_sample_ttl(cycle_s):
    """Five cycles of slack, never under 5 s, so one slow Modbus cycle does not
    make keys flicker. Returns the value applied."""
    import math
    global SAMPLE_TTL_SEC
    SAMPLE_TTL_SEC = max(5, int(math.ceil(float(cycle_s) * 5)))
    return SAMPLE_TTL_SEC


# Collector heartbeat — same idiom as the host's `host_ttl`: SET + EXPIRE every
# cycle on both backends; key presence = the collector loop is alive. This is
# the only liveness signal on the legacy (ADS1256) path, where COMM_STATUS is
# never written.
COLLECTOR_TTL = 'collector_ttl'
