"""PCB Modbus read → decode → Redis SET.

Reads NTC, DIN, AIN, and Pulse Freq in one cycle and publishes to Redis.
The NTC -999 sentinel (disconnected) causes the key itself to be DELed, so the exporter
excludes it automatically.
ΔT is computed only when both inlet and outlet of a pair are valid.

The pump/fan PWM duty keys and fan_rpm keys are SET (sticky) only for channels mapped in
wiring whose Tach signal has been observed at least once. If a pump/fan is physically
unplugged, the motor won't spin even when the PCB drives it, so tach=0 → the key is never
SET → the exporter's `client.exists()` gate excludes it automatically.

Leak detection: compares the PCB **AIN CH8** voltage register (IR 39, 0.01 V units, 0~10.5 V
full scale) against a threshold → wet ~= 0 V, dry ~= 10.5 V (measured). Single reads are
noisy, so an N-of-M majority filter is applied to suppress chattering (5-sample window,
confirmed on 3+ agreement). Level uses the DIN2 digital signal (IR 25 bit) with the same
debounce.
"""
import logging
from collections import deque

from . import registers as R
from . import redis_keys as K
from .modbus_client import s16

log = logging.getLogger(__name__)


# ==============================================
# Connection-detection sticky state - accumulated over the service lifetime
# (Once tach > 0 is seen, mark the channel "connected". The flag survives transient stops
# or seizures dropping back to 0 and only resets on service restart.)
# ==============================================
_pump_connected = set()    # logical indices (0-based)
_fan_connected = set()


# ==============================================
# DIN debounce - N-of-M majority filter for leak/level signals
# WINDOW=5, THRESHOLD=3 → stable confirmed state within ~3 s on a 1 s cycle
# ==============================================
_DIN_WINDOW = 5
_DIN_THRESHOLD = 3   # majority means 3+ out of 5
_leak_history = deque(maxlen=_DIN_WINDOW)
_level_history = deque(maxlen=_DIN_WINDOW)
# Confirmed-state cache. None means we haven't confirmed yet (raw passes through during the
# first N cycles).
_leak_confirmed = None
_level_confirmed = None


def _debounce(history, current_raw, prev_confirmed):
    """N-of-M majority filter. Raw passes through until WINDOW is filled, then majority rules.

    history: deque(maxlen=N), accumulates the last N raw values
    current_raw: this cycle's 0/1
    prev_confirmed: most recent confirmed state (None if not yet confirmed)
    """
    history.append(current_raw)
    if len(history) < _DIN_WINDOW:
        # Warmup - pass raw through (for fast response right after power-on)
        return current_raw
    leak_count = sum(history)
    if leak_count >= _DIN_THRESHOLD:
        return 1
    if leak_count <= _DIN_WINDOW - _DIN_THRESHOLD:
        return 0
    # Hysteresis region (theoretically unreachable with N=5,T=3; safety net)
    return prev_confirmed if prev_confirmed is not None else current_raw


def poll_once(pcb, rd, cfg):
    """One polling cycle. Returns True if all PCB reads succeeded.

    cfg is the full control_board config (uses both the wiring and pump sections).
    """
    wiring = cfg.get('wiring', {}) or {}
    pump_cfg = cfg.get('pump', {}) or {}
    pipe = rd.pipeline(transaction=False)

    # === NTC (IR 28~31, signed int16, 0.1°C, -999=no sensor) ===
    ntcs = pcb.read_input_registers(R.IR_NTC_TEMP_BASE, 4)
    if ntcs is None:
        return False

    ntc_map = wiring.get('ntc', {}) or {}
    ntc_values = {}      # logical ('inlet1', etc.) → temp °C or None
    for logical, ch in ntc_map.items():
        if ch is None:
            continue
        idx = ch - 13  # CH13~16 → IR 28~31 → list index 0~3
        if not (0 <= idx < 4):
            continue
        signed = s16(ntcs[idx])
        rkey = K.NTC_LOGICAL_TO_KEY.get(logical)
        if rkey is None:
            continue
        if signed == R.NTC_DISCONNECT_SENTINEL:
            pipe.delete(rkey)
            ntc_values[logical] = None
        else:
            temp_c = round(signed / 10.0, 1)
            pipe.set(rkey, temp_c)
            ntc_values[logical] = temp_c

    _delta_t(pipe, ntc_values, 'inlet1', 'outlet1', K.COOLANT_DELTA_T1)
    _delta_t(pipe, ntc_values, 'inlet2', 'outlet2', K.COOLANT_DELTA_T2)

    global _leak_confirmed, _level_confirmed

    # === Level: DIN (IR 25 bitmask) - N-of-M debounce ===
    din_regs = pcb.read_input_registers(R.IR_DIN_BITMASK, 1)
    if din_regs is None:
        return False
    bits = din_regs[0]
    din_map = wiring.get('din', {}) or {}
    level_bit = din_map.get('level_bit')
    if level_bit is not None:
        # active-high assumed: bit=1 → OK (HIGH), bit=0 → low
        raw = 1 if (bits >> level_bit) & 1 else 0
        _level_confirmed = _debounce(_level_history, raw, _level_confirmed)
        pipe.set(K.COOLANT_LEVEL, _level_confirmed)

    # === Leak: AIN voltage (IR 32~39, 0.01 V units) - threshold + debounce ===
    # PCB measures the external 0~10 V via a 1:2 divider → wet ~= 0 V, dry ~= 4.3 V
    # (measured 2026-05-04). leak=1 when below the threshold.
    ain_map = wiring.get('ain', {}) or {}
    leak_ch = ain_map.get('leak_ch')
    if leak_ch is not None and 1 <= leak_ch <= 8:
        voltages = pcb.read_input_registers(R.IR_VOLTAGE_BASE, 8)
        if voltages is None:
            return False
        v_reg = voltages[leak_ch - 1]                              # 0.01 V units
        threshold_reg = int(float(ain_map.get('leak_threshold_v', 5.0)) * 100)
        raw = 1 if v_reg < threshold_reg else 0
        _leak_confirmed = _debounce(_leak_history, raw, _leak_confirmed)
        pipe.set(K.COOLANT_LEAK, _leak_confirmed)

    # === Pulse Freq (IR 13~24) ===
    # Fans: shown as Tach RPM. Pumps: used for flow estimation. Both feed sticky connection detection.
    pulses = pcb.read_input_registers(R.IR_PULSE_FREQ_BASE, 12)
    if pulses is None:
        return False

    pwm_map = wiring.get('pwm', {}) or {}
    pump_pwm_chs = pwm_map.get('pump_ch') or []
    fan_pwm_chs = pwm_map.get('fan_ch') or []

    # Sticky connection detection: only register channels where tach > 0 has been observed at least once.
    # Assumption: the Tach for PWM output CH N is routed to the matching Pulse input CH N.
    # Indices are 0-based (matches display profile / GPU/CPU conventions).
    for i, ch in enumerate(pump_pwm_chs):
        if 1 <= ch <= 12 and pulses[ch - 1] > 0:
            _pump_connected.add(i)
    for i, ch in enumerate(fan_pwm_chs):
        if 1 <= ch <= 12 and pulses[ch - 1] > 0:
            _fan_connected.add(i)

    # Fan RPM - SET only confirmed-connected channels (2 p/r → RPM = Hz x 30)
    for i, ch in enumerate(fan_pwm_chs):
        if i in _fan_connected and 1 <= ch <= 12:
            pipe.set(K.fan_rpm(i), pulses[ch - 1] * 30)
        else:
            pipe.delete(K.fan_rpm(i))

    # === PWM duty readback (HR 0~11) ===
    duties = pcb.read_holding_registers(R.HR_PWM_DUTY_BASE, 12)
    if duties is None:
        return False

    # PWM duty - SET only confirmed-connected channels, DEL the rest (UI excludes them automatically)
    for i, ch in enumerate(pump_pwm_chs):
        if i in _pump_connected and 1 <= ch <= 12:
            pipe.set(K.pwm_duty_pump(i), duties[ch - 1])
        else:
            pipe.delete(K.pwm_duty_pump(i))
    for i, ch in enumerate(fan_pwm_chs):
        if i in _fan_connected and 1 <= ch <= 12:
            pipe.set(K.pwm_duty_fan(i), duties[ch - 1])
        else:
            pipe.delete(K.pwm_duty_fan(i))

    # === Pump flow estimation (uses the average duty of confirmed-connected pumps) ===
    connected_pump_duties = [
        duties[ch - 1]
        for i, ch in enumerate(pump_pwm_chs)
        if i in _pump_connected and 1 <= ch <= 12
    ]
    if connected_pump_duties and pump_cfg:
        avg_duty = sum(connected_pump_duties) / len(connected_pump_duties)
        max_lpm = float(pump_cfg.get('max_flow_lpm', 16))
        mult = float(pump_cfg.get('flow_multiplier', 1.0))
        flow_lpm = max_lpm * (avg_duty / 1000.0) * mult
        pipe.set(K.COOLANT_FLOW_LPM, round(flow_lpm, 2))
    else:
        pipe.delete(K.COOLANT_FLOW_LPM)

    pipe.execute()
    return True


def _delta_t(pipe, ntcs, in_logical, out_logical, dest_key):
    i = ntcs.get(in_logical)
    o = ntcs.get(out_logical)
    if i is not None and o is not None:
        pipe.set(dest_key, round(o - i, 2))
    else:
        pipe.delete(dest_key)
