"""PCB(Gen3 제어보드) Modbus 드라이버 — 연결, health check, 센서 poll, 액추에이터 write.

control_board 패키지의 modbus_client + registers + polling + main(_resolve/apply_*)을
단일 파일로 흡수. 백엔드 family 선택은 detect_backend()가 ADS1256 존재 여부로 결정한다
(부팅 1회 Modbus probe 아님 — Rev_C는 메인보드 전원에 따라 PCB가 cycling하므로
liveness는 매 cycle health_check()로 추적).

레지스터 맵: 보드 매뉴얼 §4 Rev2.
"""
import logging
from collections import deque

from pymodbus.client import ModbusSerialClient

import redis_keys as K

log = logging.getLogger('pcb_driver')


# ──────────────────────────────────────────────────────────────────
# 레지스터 맵 (구 registers.py)
# ──────────────────────────────────────────────────────────────────
# Holding Registers (FC 03/06/10) — Read/Write
HR_PWM_DUTY_BASE  = 0      # CH1~12 → 0~11 (0~1000 = 0.0~100.0%)
HR_PWM_FREQ_TIM1  = 12     # CH1~4 freq (Hz)
HR_PWM_FREQ_TIM2  = 13     # CH5~8 freq
HR_PWM_FREQ_TIM8  = 14     # CH9~12 freq
HR_DOUT_BITMASK   = 15     # bit0~5 = DOUT1~6

# Input Registers (FC 04) — Read Only
IR_SYSTEM_TIMER    = 0     # seconds (health check 대상)
IR_PULSE_FREQ_BASE = 13    # CH1~12 → 13~24 (Hz)
IR_DIN_BITMASK     = 25    # bit0~5 = DIN1~6
IR_NTC_TEMP_BASE   = 28    # CH13~16 → 28~31 (signed int16, 0.1°C; -999=no sensor)
IR_VOLTAGE_BASE    = 32    # CH1~8 → 32~39 (0.01 V)

NTC_DISCONNECT_SENTINEL = -999

# Modbus 타이밍 — 로컬 UART(115200) + MCU 응답 수 ms라 짧게 잡아도 충분.
# retries=0: PCB OFF 시(메인보드 cycling) 한 read가 길게 막혀 env 상시 센싱을
# 굶기지 않도록. liveness는 health_check 실패 누적으로 별도 판단.
_MODBUS_TIMEOUT = 0.3


def hr_pwm_duty(ch1to12):
    return HR_PWM_DUTY_BASE + (ch1to12 - 1)


def s16(u16):
    """Unsigned 16-bit → signed (NTC -999 sentinel용)."""
    return u16 - 0x10000 if u16 >= 0x8000 else u16


def detect_backend():
    """백엔드 family 결정 — ADS1256(Pi SPI 보드, 전원 무관·결정적) 존재 여부.

    'legacy' = ADS1256 장착 (Gen1~2), 'pcb' = ADS1256 미장착 (Gen3 제어보드).
    """
    import dlc_sensors
    return 'legacy' if dlc_sensors._ADC_AVAILABLE else 'pcb'


class PCBDriver:
    """PCB Modbus client + sensor read + actuator write.

    포트(`/dev/serial0` 등)는 Pi UART라 PCB 전원과 무관하게 상존 → 한 번 열어두고
    재사용. PCB가 OFF면 read만 timeout. 켜진 baud/port는 첫 응답 때 lock 된다.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        mb = cfg['modbus']
        self.ports = mb['port'] if isinstance(mb['port'], list) else [mb['port']]
        self.bauds = mb['baud'] if isinstance(mb['baud'], list) else [mb['baud']]
        self.slave = int(mb['slave'])
        self.cli = None          # locked ModbusSerialClient
        self.port = None
        self.baud = None

        # polling sticky/debounce 상태 (구 polling.py 모듈 전역 → 인스턴스)
        self._pump_connected = set()
        self._fan_connected = set()
        self._din_window = 5
        self._din_threshold = 3
        self._leak_history = deque(maxlen=self._din_window)
        self._level_history = deque(maxlen=self._din_window)
        self._leak_confirmed = None
        self._level_confirmed = None

    # ── 연결 / liveness ────────────────────────────────────────────
    def _make_client(self, port, baud):
        return ModbusSerialClient(
            port=port, baudrate=int(baud), parity='N',
            stopbits=1, bytesize=8, timeout=_MODBUS_TIMEOUT, retries=0,
        )

    def _probe(self, cli):
        try:
            rr = cli.read_input_registers(IR_SYSTEM_TIMER, count=1, device_id=self.slave)
            return rr is not None and not rr.isError()
        except Exception:
            return False

    def health_check(self):
        """살아있으면 True. baud/port 미확정이면 후보를 순회해 lock 시도.

        PCB OFF 시 빠르게 False 반환(retries=0, short timeout)하여 메인 루프가
        env 상시 센싱으로 진행하도록 한다.
        """
        if self.cli is not None:
            if self._probe(self.cli):
                return True
            # lock 됐던 PCB가 사라짐(메인보드 OFF) — 포트는 유지, 다음 cycle 재시도
            return False

        # 아직 baud/port 미확정 — 후보 순회 (PCB가 막 켜졌을 수 있음)
        for port in self.ports:
            for baud in self.bauds:
                cli = self._make_client(port, baud)
                try:
                    if cli.connect() and self._probe(cli):
                        self.cli, self.port, self.baud = cli, port, int(baud)
                        log.info("PCB locked on %s @ %d, slave %d", port, self.baud, self.slave)
                        return True
                except Exception:
                    pass
                try:
                    cli.close()
                except Exception:
                    pass
        return False

    def close(self):
        if self.cli is not None:
            try:
                self.cli.close()
            except Exception:
                pass

    # ── 저수준 R/W ────────────────────────────────────────────────
    def read_input_registers(self, address, count):
        if self.cli is None:
            return None
        try:
            rr = self.cli.read_input_registers(address, count=count, device_id=self.slave)
            if rr is None or rr.isError():
                return None
            return rr.registers
        except Exception:
            return None

    def read_holding_registers(self, address, count):
        if self.cli is None:
            return None
        try:
            rr = self.cli.read_holding_registers(address, count=count, device_id=self.slave)
            if rr is None or rr.isError():
                return None
            return rr.registers
        except Exception:
            return None

    def write_register(self, address, value):
        if self.cli is None:
            return False
        try:
            rr = self.cli.write_register(address, value, device_id=self.slave)
            return rr is not None and not rr.isError()
        except Exception:
            return False

    def write_registers(self, address, values):
        if self.cli is None:
            return False
        try:
            rr = self.cli.write_registers(address, values, device_id=self.slave)
            return rr is not None and not rr.isError()
        except Exception:
            return False

    # ── 초기 상태 적용 (구 main.apply_*) ──────────────────────────
    def apply_pwm_freq(self):
        freq = self.cfg.get('pwm_freq') or {}
        applied = {}
        for hr, key in ((HR_PWM_FREQ_TIM1, 'tim1'),
                        (HR_PWM_FREQ_TIM2, 'tim2'),
                        (HR_PWM_FREQ_TIM8, 'tim8')):
            v = freq.get(key)
            if v is None:
                continue
            self.write_register(hr, int(v))
            applied[key] = int(v)
        log.info("PWM freq applied: %s", applied or 'none')

    def apply_initial_state(self):
        """Flash 미저장 항목(PWM duty, DOUT) 적용 — 부팅/복구 시."""
        duty_cfg = self.cfg.get('initial_pwm_duty', {}) or {}
        pump = duty_cfg.get('pump') or {}
        fan = duty_cfg.get('fan') or {}
        for ch in range(1, 5):
            self.write_register(hr_pwm_duty(ch), int(pump.get(f'ch{ch}', 0)))
        for ch in range(5, 13):
            self.write_register(hr_pwm_duty(ch), int(fan.get(f'ch{ch}', 0)))
        self.write_register(HR_DOUT_BITMASK, int(self.cfg.get('initial_dout_bitmask', 0)))
        log.info("initial PWM duty + DOUT applied")

    def on_connect(self, rd):
        """PCB down→up 전이 시 1회 — freq/duty 재적용 + comm 상태 초기화."""
        self.apply_pwm_freq()
        self.apply_initial_state()
        rd.set(K.COMM_STATUS, 'ok')
        rd.set(K.COMM_CONSECUTIVE_FAILURES, 0)

    def set_config(self, cfg):
        """핫리로드된 cfg 반영 (modbus 섹션은 런타임 변경 안 함)."""
        self.cfg = cfg

    # ── 센서 poll (구 polling.poll_once) ──────────────────────────
    def poll(self, rd):
        """One polling cycle. coolant_*, leak, level, flow, fan_rpm, pwm_duty 갱신.

        env(air_temp/humit)·chassis는 PCB가 아니라 Pi 직결이라 여기서 다루지 않는다.
        Returns True if all PCB reads succeeded.
        """
        cfg = self.cfg
        wiring = cfg.get('wiring', {}) or {}
        pump_cfg = cfg.get('pump', {}) or {}
        pipe = rd.pipeline(transaction=False)

        # ── NTC (IR 28~31, signed int16, 0.1°C, -999=no sensor) ──
        ntcs = self.read_input_registers(IR_NTC_TEMP_BASE, 4)
        if ntcs is None:
            return False
        ntc_map = wiring.get('ntc', {}) or {}
        ntc_values = {}
        for logical, ch in ntc_map.items():
            if ch is None:
                continue
            idx = ch - 13                      # CH13~16 → IR 28~31 → index 0~3
            if not (0 <= idx < 4):
                continue
            rkey = K.NTC_LOGICAL_TO_KEY.get(logical)
            if rkey is None:
                continue
            signed = s16(ntcs[idx])
            if signed == NTC_DISCONNECT_SENTINEL:
                pipe.delete(rkey)
                ntc_values[logical] = None
            else:
                temp_c = round(signed / 10.0, 1)
                pipe.set(rkey, temp_c)
                ntc_values[logical] = temp_c

        self._delta_t(pipe, ntc_values, 'inlet1', 'outlet1', K.COOLANT_DELTA_T1)
        self._delta_t(pipe, ntc_values, 'inlet2', 'outlet2', K.COOLANT_DELTA_T2)

        # ── 수위: DIN (IR 25 bitmask) — N-of-M debounce ──
        din_regs = self.read_input_registers(IR_DIN_BITMASK, 1)
        if din_regs is None:
            return False
        bits = din_regs[0]
        din_map = wiring.get('din', {}) or {}
        level_bit = din_map.get('level_bit')
        if level_bit is not None:
            raw = 1 if (bits >> level_bit) & 1 else 0
            self._level_confirmed = self._debounce(self._level_history, raw, self._level_confirmed)
            pipe.set(K.COOLANT_LEVEL, self._level_confirmed)

        # ── 누수: AIN voltage (IR 32~39, 0.01V) — threshold + debounce ──
        ain_map = wiring.get('ain', {}) or {}
        leak_ch = ain_map.get('leak_ch')
        if leak_ch is not None and 1 <= leak_ch <= 8:
            voltages = self.read_input_registers(IR_VOLTAGE_BASE, 8)
            if voltages is None:
                return False
            v_reg = voltages[leak_ch - 1]
            threshold_reg = int(float(ain_map.get('leak_threshold_v', 5.0)) * 100)
            raw = 1 if v_reg < threshold_reg else 0
            self._leak_confirmed = self._debounce(self._leak_history, raw, self._leak_confirmed)
            pipe.set(K.COOLANT_LEAK, self._leak_confirmed)

        # ── Pulse Freq (IR 13~24) — fan tach / pump 연결 감지 ──
        pulses = self.read_input_registers(IR_PULSE_FREQ_BASE, 12)
        if pulses is None:
            return False
        pwm_map = wiring.get('pwm', {}) or {}
        pump_pwm_chs = pwm_map.get('pump_ch') or []
        fan_pwm_chs = pwm_map.get('fan_ch') or []

        for i, ch in enumerate(pump_pwm_chs):
            if 1 <= ch <= 12 and pulses[ch - 1] > 0:
                self._pump_connected.add(i)
        for i, ch in enumerate(fan_pwm_chs):
            if 1 <= ch <= 12 and pulses[ch - 1] > 0:
                self._fan_connected.add(i)

        for i, ch in enumerate(fan_pwm_chs):
            if i in self._fan_connected and 1 <= ch <= 12:
                pipe.set(K.fan_rpm(i), pulses[ch - 1] * 30)   # 2 p/r → RPM = Hz × 30
            else:
                pipe.delete(K.fan_rpm(i))

        # ── PWM duty readback (HR 0~11) ──
        duties = self.read_holding_registers(HR_PWM_DUTY_BASE, 12)
        if duties is None:
            return False
        for i, ch in enumerate(pump_pwm_chs):
            if i in self._pump_connected and 1 <= ch <= 12:
                pipe.set(K.pwm_duty_pump(i), duties[ch - 1])
            else:
                pipe.delete(K.pwm_duty_pump(i))
        for i, ch in enumerate(fan_pwm_chs):
            if i in self._fan_connected and 1 <= ch <= 12:
                pipe.set(K.pwm_duty_fan(i), duties[ch - 1])
            else:
                pipe.delete(K.pwm_duty_fan(i))

        # ── 펌프 유량 추정 (연결 확인된 펌프 duty 평균) ──
        connected_pump_duties = [
            duties[ch - 1]
            for i, ch in enumerate(pump_pwm_chs)
            if i in self._pump_connected and 1 <= ch <= 12
        ]
        if connected_pump_duties and pump_cfg:
            avg_duty = sum(connected_pump_duties) / len(connected_pump_duties)
            max_lpm = float(pump_cfg.get('max_flow_lpm', 16))
            mult = float(pump_cfg.get('flow_multiplier', 1.0))
            pipe.set(K.COOLANT_FLOW_LPM, round(max_lpm * (avg_duty / 1000.0) * mult, 2))
        else:
            pipe.delete(K.COOLANT_FLOW_LPM)

        pipe.execute()
        return True

    # ── helpers ────────────────────────────────────────────────────
    def _delta_t(self, pipe, ntcs, in_logical, out_logical, dest_key):
        i = ntcs.get(in_logical)
        o = ntcs.get(out_logical)
        if i is not None and o is not None:
            pipe.set(dest_key, round(o - i, 2))
        else:
            pipe.delete(dest_key)

    def _debounce(self, history, current_raw, prev_confirmed):
        """N-of-M majority filter. WINDOW 채우기 전엔 raw 통과."""
        history.append(current_raw)
        if len(history) < self._din_window:
            return current_raw
        count = sum(history)
        if count >= self._din_threshold:
            return 1
        if count <= self._din_window - self._din_threshold:
            return 0
        return prev_confirmed if prev_confirmed is not None else current_raw
