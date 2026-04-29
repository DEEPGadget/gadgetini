"""PCB Modbus Read → 디코딩 → Redis SET.

NTC, DIN, Pulse Freq를 한 cycle에 읽고 Redis로 publish.
NTC -999 sentinel(미연결)은 키 자체를 DEL하여 exporter 측에서 자동 제외.
inlet/outlet 페어가 둘 다 valid일 때만 ΔT 계산.

펌프/팬 PWM duty 키와 fan_rpm 키는 wiring에 매핑된 채널 중 **Tach 신호가 한 번이라도
관측된** 채널만 SET (sticky). 펌프/팬이 물리적으로 미연결이면 PCB가 신호를 보내도
모터가 안 돌아 tach=0 → 키 자체 SET 안 됨 → exporter `client.exists()` 게이트로 자동 제외.
"""
import logging

from . import registers as R
from . import redis_keys as K
from .modbus_client import s16

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 연결 감지 sticky state — service lifetime 동안 누적
# (한 번이라도 tach > 0 이면 "연결됨"으로 표시. 일시적 정지/seizure로 0으로 떨어져도
# 유지되며, 서비스 재시작 시 초기화된다.)
# ──────────────────────────────────────────────
_pump_connected = set()    # 논리 인덱스 (1-based)
_fan_connected = set()


def poll_once(pcb, rd, cfg):
    """One polling cycle. Returns True if all PCB reads succeeded.

    cfg는 control_board config 전체 (wiring, pump 섹션 모두 사용).
    """
    wiring = cfg.get('wiring', {}) or {}
    pump_cfg = cfg.get('pump', {}) or {}
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
    # 팬은 Tach RPM 표시, 펌프는 유량 추정. 양쪽 모두 sticky 연결 감지에 사용.
    pulses = pcb.read_input_registers(R.IR_PULSE_FREQ_BASE, 12)
    if pulses is None:
        return False

    pwm_map = wiring.get('pwm', {}) or {}
    pump_pwm_chs = pwm_map.get('pump_ch') or []
    fan_pwm_chs = pwm_map.get('fan_ch') or []

    # 연결 감지 sticky: tach > 0 이 한 번이라도 관측된 채널만 등록.
    # 가정: PWM 출력 CH N의 Tach가 같은 번호 Pulse 입력 CH N으로 라우팅.
    # 인덱스는 0-based (display profile / GPU/CPU 컨벤션과 일치).
    for i, ch in enumerate(pump_pwm_chs):
        if 1 <= ch <= 12 and pulses[ch - 1] > 0:
            _pump_connected.add(i)
    for i, ch in enumerate(fan_pwm_chs):
        if 1 <= ch <= 12 and pulses[ch - 1] > 0:
            _fan_connected.add(i)

    # 팬 RPM — 연결 확인된 채널만 SET (2 p/r → RPM = Hz × 30)
    for i, ch in enumerate(fan_pwm_chs):
        if i in _fan_connected and 1 <= ch <= 12:
            pipe.set(K.fan_rpm(i), pulses[ch - 1] * 30)
        else:
            pipe.delete(K.fan_rpm(i))

    # ── PWM duty readback (HR 0~11) ──
    duties = pcb.read_holding_registers(R.HR_PWM_DUTY_BASE, 12)
    if duties is None:
        return False

    # PWM duty — 연결 확인된 채널만 SET, 나머지는 DEL (UI에서 자동 제외)
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

    # ── 펌프 유량 추정 (연결 확인된 펌프 duty의 평균 사용) ──
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
