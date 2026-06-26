"""Control-board cooling policy — fan-duty control + config hot-reload.

Fan duty is a linear interpolation of outlet1 temperature between (min_temp, min_duty)
and (max_temp, max_duty). Pump duty is fixed (no flow sensor). There is no state
machine: the 12V supply being mainboard-gated is the hardware interlock.

Hot-reload: on a pcb_config.yaml mtime change, fan_curve / pump duty / DOUT are applied
at runtime (web UI edit -> REST API -> file write -> picked up next cycle).
"""
import logging
import os

import yaml

import pcb_driver
import redis_keys as K

log = logging.getLogger('pcb_control')

# Skip the Modbus write if duty moved less than this (avoid per-cycle writes on noise).
_WRITE_DEADBAND = 5  # 0.5%


def _contiguous_runs(channels):
    """[8,9,10,12] -> [(8,[8,9,10]), (12,[12])] — group consecutive channels."""
    if not channels:
        return []
    sorted_chs = sorted(set(channels))
    runs = []
    start = sorted_chs[0]
    cur = [start]
    for ch in sorted_chs[1:]:
        if ch == cur[-1] + 1:
            cur.append(ch)
        else:
            runs.append((start, cur))
            start = ch
            cur = [ch]
    runs.append((start, cur))
    return runs


class FanCurveController:
    """Linear interpolation between (min_temp, min_duty) and (max_temp, max_duty)."""

    def __init__(self, fan_curve_cfg, fan_pwm_chs):
        cfg = fan_curve_cfg or {}
        self.min_temp = float(cfg.get('min_temp', 25))
        self.max_temp = float(cfg.get('max_temp', 60))
        self.min_duty = int(cfg.get('min_duty', 80))
        self.max_duty = int(cfg.get('max_duty', 1000))
        if self.max_temp <= self.min_temp:
            self.max_temp = self.min_temp + 1.0
        self.fan_chs = list(fan_pwm_chs or [])
        # Consecutive channels are written in one FC16 transaction (atomic).
        self._runs = _contiguous_runs(self.fan_chs)
        self._last_written = None

    def _compute_duty(self, temp_c):
        if temp_c <= self.min_temp:
            return self.min_duty
        if temp_c >= self.max_temp:
            return self.max_duty
        frac = (temp_c - self.min_temp) / (self.max_temp - self.min_temp)
        return int(round(self.min_duty + frac * (self.max_duty - self.min_duty)))

    def update(self, pcb, rd):
        """Read outlet1 -> compute duty -> write to all configured fan channels.

        The Web UI reads duty back via PCBDriver.poll (register readback), so this
        only writes the channels; it does not publish to Redis itself.
        """
        if not self.fan_chs:
            return
        v = rd.get(K.COOLANT_TEMP_OUTLET1)
        temp_c = None
        if v is not None:
            try:
                temp_c = float(v)
            except (TypeError, ValueError):
                temp_c = None
        if temp_c is None:
            # No outlet temp (NTC unwired / read failed) — fall back to idle (min_duty).
            # Never leave duty at 0 because 0 PWM = fan runs at 100% (no control signal).
            log.warning("no %s — fan duty -> min_duty (idle baseline %d)", K.COOLANT_TEMP_OUTLET1, self.min_duty)
            duty = self.min_duty
        else:
            duty = self._compute_duty(temp_c)

        # deadband, but always emit once when reaching the min/max clamp
        if self._last_written is not None and abs(duty - self._last_written) < _WRITE_DEADBAND:
            if duty in (self.min_duty, self.max_duty) and self._last_written != duty:
                pass
            else:
                return
        for first_ch, run in self._runs:
            base_hr = pcb_driver.hr_pwm_duty(first_ch)
            if len(run) == 1:
                ok = pcb.write_register(base_hr, duty)
            else:
                ok = pcb.write_registers(base_hr, [duty] * len(run))
            if not ok:
                log.warning("fan duty write failed: CH %s (HR %d) duty=%d", run, base_hr, duty)

        self._last_written = duty
        log.debug("outlet=%s C -> duty=%d -> CH %s", temp_c, duty, self.fan_chs)


def _fan_chs(cfg):
    return (cfg.get('wiring', {}).get('pwm') or {}).get('fan_ch') or []


def make_controller(cfg):
    return FanCurveController(cfg.get('fan_curve', {}), _fan_chs(cfg))


class ConfigReloader:
    """Watches pcb_config.yaml mtime and rebuilds cfg/controller on change.

    Pump duty / DOUT are re-written only when they actually change (fan duty is
    written by the controller anyway). A failed reload keeps the previous cfg.
    """

    def __init__(self, config_path, cfg):
        self.path = config_path
        self.cfg = cfg
        self.controller = make_controller(cfg)
        self.last_mtime = self._mtime()
        self.last_pump = self._pump_duties(cfg)
        self.last_dout = int(cfg.get('initial_dout_bitmask', 0))

    def _mtime(self):
        try:
            return os.path.getmtime(self.path)
        except OSError:
            return None

    @staticmethod
    def _pump_duties(cfg):
        pump = (cfg.get('initial_pwm_duty', {}) or {}).get('pump') or {}
        return {k: int(v) for k, v in pump.items()}

    def maybe_reload(self, driver):
        """Reload on change and apply to driver; always returns the current controller."""
        m = self._mtime()
        if m is None or m == self.last_mtime:
            return self.controller
        try:
            with open(self.path) as f:
                new_cfg = yaml.safe_load(f)
            new_controller = make_controller(new_cfg)
            new_pump = self._pump_duties(new_cfg)
            new_dout = int(new_cfg.get('initial_dout_bitmask', 0))
            driver.set_config(new_cfg)
            if new_pump != self.last_pump or new_dout != self.last_dout:
                driver.apply_initial_state()
                self.last_pump = new_pump
                self.last_dout = new_dout
            self.cfg = new_cfg
            self.controller = new_controller
            self.last_mtime = m
            log.info("pcb_config.yaml reloaded (mtime change)")
        except Exception:
            log.exception("config reload failed; keeping previous cfg")
            self.last_mtime = m   # don't retry the same broken file every cycle
        return self.controller
