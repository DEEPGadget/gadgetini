"""Control-board cooling policy — multi-source fan-duty control + config hot-reload.

Fan duty is computed from multiple temperature sources (coolant, chassis, etc.), each
with its own linear interpolation between (min_temp, min_duty) and (max_temp, max_duty).
The final duty is the maximum across all sources. Pump duty is fixed (no flow sensor).
There is no state machine: the 12V supply being mainboard-gated is the hardware interlock.

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


class _CurveSource:
    """Single temperature source for fan curve (min/max temp/duty, linear interpolation)."""

    def __init__(self, src_cfg):
        self.key = src_cfg.get('key', 'unknown')
        self.label = src_cfg.get('label', self.key)
        self.redis_key = src_cfg.get('redis_key', '')
        self.min_temp = float(src_cfg.get('min_temp', 25))
        self.max_temp = float(src_cfg.get('max_temp', 60))
        self.min_duty = int(src_cfg.get('min_duty', 80))
        self.max_duty = int(src_cfg.get('max_duty', 1000))
        if self.max_temp <= self.min_temp:
            self.max_temp = self.min_temp + 1.0

    def compute(self, rd):
        """Read temp from Redis, compute duty, return (duty, temp_c)."""
        v = rd.get(self.redis_key)
        temp_c = None
        if v is not None:
            try:
                temp_c = float(v)
            except (TypeError, ValueError):
                temp_c = None

        if temp_c is None:
            duty = self.min_duty
            log.debug("%s: no %s — duty -> min_duty (idle baseline %d)", self.key, self.redis_key, self.min_duty)
        else:
            if temp_c <= self.min_temp:
                duty = self.min_duty
            elif temp_c >= self.max_temp:
                duty = self.max_duty
            else:
                frac = (temp_c - self.min_temp) / (self.max_temp - self.min_temp)
                duty = int(round(self.min_duty + frac * (self.max_duty - self.min_duty)))

        return duty, temp_c


class FanCurveController:
    """Multi-source fan curve: max(duty) across all sources, per-source linear interpolation."""

    def __init__(self, fan_curve_cfg, fan_pwm_chs):
        cfg = fan_curve_cfg or {}
        self.sources = [_CurveSource(s) for s in cfg.get('sources', [])]
        self.fan_chs = list(fan_pwm_chs or [])
        # Consecutive channels are written in one FC16 transaction (atomic).
        self._runs = _contiguous_runs(self.fan_chs)
        self._last_written = None
        self._last_winner = None

    def update(self, pcb, rd):
        """Compute duty from all sources, take max, write to fan channels, publish to Redis.

        Per-source duty values are published to Redis for UI breakdown; the selected
        (winning) source key is published to PWM_CURVE_SELECTED_SOURCE.
        The Web UI reads duty back via PCBDriver.poll (register readback), so we also
        publish per-source computed duties separately.
        """
        if not self.fan_chs or not self.sources:
            return

        results = []
        for src in self.sources:
            duty, temp_c = src.compute(rd)
            results.append((src, duty, temp_c))

        if not results:
            return

        winner_src, duty, winner_temp = max(results, key=lambda r: r[1])

        # deadband, but always emit once when reaching the min/max clamp
        if self._last_written is not None and abs(duty - self._last_written) < _WRITE_DEADBAND:
            if duty in (winner_src.min_duty, winner_src.max_duty) and self._last_written != duty:
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
        self._last_winner = winner_src.key

        pipe = rd.pipeline()
        for src, src_duty, _ in results:
            pipe.set(K.pwm_curve_source_duty(src.key), src_duty)
        pipe.set(K.PWM_CURVE_SELECTED_SOURCE, winner_src.key)
        pipe.execute()

        log.debug("fan duty: max(%s) = %d (winner: %s) -> CH %s",
                  ', '.join(f"{src.key}={d}" for src, d, _ in results), duty, winner_src.key, self.fan_chs)


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
