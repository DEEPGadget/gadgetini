"""PCB Modbus Read → 디코딩 → Redis SET.

NTC, DIN, Pulse Freq를 한 cycle에 읽고 Redis로 publish.
NTC -999 sentinel(미연결)은 키 자체를 DEL하여 exporter 측에서 자동 제외.
inlet/outlet 페어가 둘 다 valid일 때만 ΔT 계산.
"""
import logging

from . import registers as R
from . import redis_keys as K
from .modbus_client import s16

log = logging.getLogger(__name__)


def poll_once(pcb, rd, wiring):
    """One polling cycle. Returns True if all PCB reads succeeded."""
    pipe = rd.pipeline(transaction=False)

    # ── NTC (IR 28~31, signed int16, 0.1°C, -999=no sensor) ──
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

    # ── DIN (IR 25 bitmask) ──
    din_regs = pcb.read_input_registers(R.IR_DIN_BITMASK, 1)
    if din_regs is None:
        return False
    bits = din_regs[0]
    din_map = wiring.get('din', {}) or {}
    leak_bit = din_map.get('leak_bit')
    level_bit = din_map.get('level_bit')
    if leak_bit is not None:
        # active-high 가정: bit=1 → 누수
        pipe.set(K.COOLANT_LEAK, 1 if (bits >> leak_bit) & 1 else 0)
    if level_bit is not None:
        # active-high 가정: bit=1 → 정상(HIGH), bit=0 → 부족
        pipe.set(K.COOLANT_LEVEL, 1 if (bits >> level_bit) & 1 else 0)

    # ── Pulse Freq (IR 13~24) ──
    pulses = pcb.read_input_registers(R.IR_PULSE_FREQ_BASE, 12)
    if pulses is None:
        return False
    pulse_map = wiring.get('pulse', {}) or {}

    pump_chs = pulse_map.get('pump_tach_chs') or []
    if pump_chs:
        rpms = [pulses[ch - 1] * 60 for ch in pump_chs]   # 1 p/r 가정 (실측 보정 필요)
        avg = int(sum(rpms) / len(rpms))
        pipe.set(K.PUMP_RPM, avg)

    fan_chs = pulse_map.get('fan_tach_chs') or []
    for i, ch in enumerate(fan_chs, start=1):
        hz = pulses[ch - 1]
        rpm = hz * 30                                      # 2 p/r → RPM = Hz × 30
        pipe.set(K.fan_rpm(i), rpm)

    # ── PWM duty readback (HR 0~11) ──
    duties = pcb.read_holding_registers(R.HR_PWM_DUTY_BASE, 12)
    if duties is None:
        return False
    pwm_map = wiring.get('pwm', {}) or {}
    for i, ch in enumerate(pwm_map.get('pump_ch') or [], start=1):
        if 1 <= ch <= 12:
            pipe.set(K.pwm_duty_pump(i), duties[ch - 1])
    for i, ch in enumerate(pwm_map.get('fan_ch') or [], start=1):
        if 1 <= ch <= 12:
            pipe.set(K.pwm_duty_fan(i), duties[ch - 1])

    pipe.execute()
    return True


def _delta_t(pipe, ntcs, in_logical, out_logical, dest_key):
    i = ntcs.get(in_logical)
    o = ntcs.get(out_logical)
    if i is not None and o is not None:
        pipe.set(dest_key, round(o - i, 2))
    else:
        pipe.delete(dest_key)
