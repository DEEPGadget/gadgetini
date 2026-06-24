"""Control-board (Gen3) Modbus driver — connect, health check, sensor poll, actuator write.

Backend family is selected by detect_backend() via ADS1256 presence, not a one-shot
Modbus probe: on Rev_C the PCB is powered from the mainboard and cycles with it, so
liveness is tracked every cycle by health_check().

Register map: board manual section 4 (Rev2).
"""
import logging
import os
from collections import deque

from pymodbus.client import ModbusSerialClient

import redis_keys as K

log = logging.getLogger('pcb_driver')


# ── Register map ───────────────────────────────────────────────────
# Holding Registers (FC 03/06/10) — R/W
HR_PWM_DUTY_BASE  = 0      # CH1~12 -> 0~11 (0~1000 = 0.0~100.0%)
HR_PWM_FREQ_TIM1  = 12     # CH1~4 freq (Hz)
HR_PWM_FREQ_TIM2  = 13     # CH5~8 freq
HR_PWM_FREQ_TIM8  = 14     # CH9~12 freq
HR_DOUT_BITMASK   = 15     # bit0~5 = DOUT1~6

# Input Registers (FC 04) — read-only
IR_SYSTEM_TIMER    = 0     # seconds (health-check target)
IR_PULSE_FREQ_BASE = 13    # CH1~12 -> 13~24 (Hz)
IR_DIN_BITMASK     = 25    # bit0~5 = DIN1~6
IR_NTC_TEMP_BASE   = 28    # CH13~16 -> 28~31 (signed int16, 0.1C; -999 = no sensor)
IR_VOLTAGE_BASE    = 32    # CH1~8 -> 32~39 (0.01 V)

NTC_DISCONNECT_SENTINEL = -999

# Short timeout + retries=0: when the PCB is off, a read must fail fast so the
# always-on env path in the main loop is never starved.
_MODBUS_TIMEOUT = 0.3


def hr_pwm_duty(ch1to12):
    return HR_PWM_DUTY_BASE + (ch1to12 - 1)


def s16(u16):
    """Unsigned 16-bit -> signed (for the NTC -999 sentinel)."""
    return u16 - 0x10000 if u16 >= 0x8000 else u16


def detect_backend():
    """'pcb' or 'legacy'.

    GADGETINI_BACKEND env var overrides auto-detect ('pcb' or 'legacy') — used on
    bench machines that have an ADS1256 attached but should run the PCB path. When
    unset/'auto', auto-detect by ADS1256 presence (a Pi SPI board, deterministic and
    independent of mainboard power): present = legacy (Gen1~2), absent = pcb (Gen3).
    """
    override = os.environ.get('GADGETINI_BACKEND', '').strip().lower()
    if override in ('pcb', 'legacy'):
        log.info("backend forced to '%s' via GADGETINI_BACKEND", override)
        return override
    import dlc_sensors
    return 'legacy' if dlc_sensors._ADC_AVAILABLE else 'pcb'


class PCBDriver:
    """Modbus client + sensor read + actuator write for the control board.

    The serial port is a Pi UART, present regardless of PCB power, so it is opened
    once and reused; when the PCB is off, reads simply time out. The live baud/port
    is locked on the first response.
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

        # sticky connection + DIN debounce state (per instance)
        self._fan_connected = set()
        self._din_window = 5
        self._din_threshold = 3
        self._leak_history = deque(maxlen=self._din_window)
        self._level_history = deque(maxlen=self._din_window)
        self._leak_confirmed = None
        self._level_confirmed = None

    # ── connect / liveness ─────────────────────────────────────────
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
        """True if alive. Locks baud/port on first response; cheap single read after."""
        if self.cli is not None:
            return self._probe(self.cli)   # locked; PCB may be off -> fail fast

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

    # ── low-level R/W ──────────────────────────────────────────────
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

    # ── initial state ──────────────────────────────────────────────
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

    def _clamp_pump_duty(self, duty):
        """Keep the pump within its rated voltage window (pump.min_duty/max_duty).

        0 = off (passed through); any non-zero drive is clamped into range so the
        pump is never driven below its minimum (e.g. 6V) or above its max (12V).
        """
        pump_cfg = self.cfg.get('pump', {}) or {}
        lo = int(pump_cfg.get('min_duty', 0))
        hi = int(pump_cfg.get('max_duty', 1000))
        if duty <= 0:
            return 0
        clamped = max(lo, min(hi, duty))
        if clamped != duty:
            log.warning("pump duty %d clamped to %d (allowed %d-%d, pump rated 6-12VDC)",
                        duty, clamped, lo, hi)
        return clamped

    def apply_initial_state(self):
        """Write non-flash-persisted state (PWM duty, DOUT) at boot/recovery."""
        duty_cfg = self.cfg.get('initial_pwm_duty', {}) or {}
        pump = duty_cfg.get('pump') or {}
        fan = duty_cfg.get('fan') or {}
        for ch in range(1, 5):
            self.write_register(hr_pwm_duty(ch), self._clamp_pump_duty(int(pump.get(f'ch{ch}', 0))))
        for ch in range(5, 13):
            self.write_register(hr_pwm_duty(ch), int(fan.get(f'ch{ch}', 0)))
        self.write_register(HR_DOUT_BITMASK, int(self.cfg.get('initial_dout_bitmask', 0)))
        log.info("initial PWM duty + DOUT applied")

    def on_connect(self, rd):
        """Run once on a PCB down->up transition: re-apply state + reset comm status."""
        self.apply_pwm_freq()
        self.apply_initial_state()
        rd.set(K.COMM_STATUS, 'ok')
        rd.set(K.COMM_CONSECUTIVE_FAILURES, 0)

    def set_config(self, cfg):
        """Apply a hot-reloaded cfg (modbus section is not changed at runtime)."""
        self.cfg = cfg

    # ── sensor poll ────────────────────────────────────────────────
    def poll(self, rd):
        """One cycle: coolant_*, leak, level, flow, fan_rpm, pwm_duty.

        Air temp/humidity are Pi-attached, not on the PCB, so they are not handled
        here. Returns True if every PCB read succeeded.
        """
        cfg = self.cfg
        wiring = cfg.get('wiring', {}) or {}
        pump_cfg = cfg.get('pump', {}) or {}
        pipe = rd.pipeline(transaction=False)

        # NTC (IR 28~31). -999 sentinel = disconnected -> delete the key.
        ntcs = self.read_input_registers(IR_NTC_TEMP_BASE, 4)
        if ntcs is None:
            return False
        ntc_map = wiring.get('ntc', {}) or {}
        ntc_values = {}
        for logical, ch in ntc_map.items():
            if ch is None:
                continue
            idx = ch - 13                      # CH13~16 -> IR 28~31 -> index 0~3
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

        # Level: DIN bit (IR 25), N-of-M debounced
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

        # Leak: AIN voltage (IR 32~39, 0.01V), threshold + debounce
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

        # Pulse freq (IR 13~24) -> sticky pump/fan connection detection
        pulses = self.read_input_registers(IR_PULSE_FREQ_BASE, 12)
        if pulses is None:
            return False
        pwm_map = wiring.get('pwm', {}) or {}
        pump_pwm_chs = pwm_map.get('pump_ch') or []

        # Sticky tach detection (fan only) by PHYSICAL slot: CH5~12 -> 0~7. A channel
        # with no tach wire reads 0 pulses and never becomes "connected".
        for ch in range(5, 13):
            if pulses[ch - 1] > 0:
                self._fan_connected.add(ch - 5)

        # Fan RPM (tach) for connected channels only (2 pulses/rev -> RPM = Hz * 30).
        for ch in range(5, 13):
            i = ch - 5
            if i in self._fan_connected:
                pipe.set(K.fan_rpm(i), pulses[ch - 1] * 30)
            else:
                pipe.delete(K.fan_rpm(i))

        # PWM duty readback (HR 0~11): published as-is for EVERY physical channel,
        # independent of tach (duty and tach are separate). pump CH1~4 -> pwm_duty_pump_0~3,
        # fan CH5~12 -> pwm_duty_fan_0~7. This includes fixed channels (e.g. CH10 RPi fan
        # @100%) that the fan curve never touches, so the UI can show them too.
        duties = self.read_holding_registers(HR_PWM_DUTY_BASE, 12)
        if duties is None:
            return False
        for ch in range(1, 5):
            pipe.set(K.pwm_duty_pump(ch - 1), duties[ch - 1])
        for ch in range(5, 13):
            pipe.set(K.pwm_duty_fan(ch - 5), duties[ch - 1])

        # Pump flow estimate (no flow sensor): from mean wired-pump commanded duty
        wired_pump_duties = [
            duties[ch - 1]
            for i, ch in enumerate(pump_pwm_chs)
            if 1 <= ch <= 12
        ]
        if wired_pump_duties and pump_cfg:
            avg_duty = sum(wired_pump_duties) / len(wired_pump_duties)
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
        """N-of-M majority filter; passes raw through until the window fills."""
        history.append(current_raw)
        if len(history) < self._din_window:
            return current_raw
        count = sum(history)
        if count >= self._din_threshold:
            return 1
        if count <= self._din_window - self._din_threshold:
            return 0
        return prev_confirmed if prev_confirmed is not None else current_raw
