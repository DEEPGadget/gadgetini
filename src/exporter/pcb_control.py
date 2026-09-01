"""Control-board cooling policy — multi-source fan-duty control + config hot-reload.

Fan duty is computed from multiple temperature sources (coolant, chassis, etc.), each
with its own linear interpolation between (min_temp, min_duty) and (max_temp, max_duty).
The final duty is the maximum across all sources. Pump duty is fixed (no flow sensor).
There is no state machine: the 12V supply being mainboard-gated is the hardware interlock.

Where the anchors come from (pcb_config.yaml; the standard/factory values live in
src/exporter/pcb_defaults.yaml, which the web UI's Reset button restores from — keep
the two in step):

  max_temp  the limit of the most heat-sensitive part in that metric's path, cross-checked
            against src/gui/grafana/common/threshold.md. Duty reaches max_duty (1000 = 100%)
            here:
              chassis 50 C  the DHT11 air sensor's own operating range is 0~50 C. Above it
                            the reading is out of spec, so duty must already be at max
                            before the measurement itself stops being trustworthy. Matches
                            threshold.md Critical >50 C. The air sensor is auto-detected
                            (HDC302x -> AHT20 -> DHT11, see dlc_sensors.py); 50 C anchors on
                            DHT11, the narrowest-range part supported, so the curve stays
                            valid on units that fall through to it.
              coolant 65 C  the PMP500 pump's allowable coolant temperature is 60~75 C.
                            65 C is the conservative end of that band and matches
                            threshold.md Critical >65 C.
            The SoCs in the box (AI processor 75 C, CPU 85 C, NIC 105 C junction) tolerate
            more than either of these, so they are not the binding constraint.
  min_temp  where the fan leaves the min_duty idle floor (80 = 8%) and starts ramping;
            27 C for both sources. Only the span between the two anchors is interpolated.
            This one is an operating-policy choice, NOT a part limit — datasheets give
            ceilings, not floors, so no part spec fixes it. See the caveat below.

Caveat on min_temp (unresolved): unlike max_temp, 27 C has no datasheet behind it. Picking it
trades idle quiet against ramp headroom: set it too low and the source never rests on the 8%
floor, but anchoring it at the threshold.md Normal ceiling (chassis 40 C, coolant 60 C) would
leave the whole Normal band with no ramp at all, so the fans would still be idling as the
metric entered Warning. It cannot be settled from the bench as things stand — no air or
coolant sensor is physically attached, so every value in Redis is simulator output, not a
measurement. Decide it from the thermal design, or from a unit with real sensors fitted.

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
        # Anchors are per-source and always come from pcb_config.yaml (see the module
        # docstring for how they map onto threshold.md); the literals below are only a
        # fallback for a malformed source entry, not the policy.
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


def apply_manual_pwm(pcb, rd, cfg):
    """Apply manual PWM targets from Redis (channel write) — no temperature feedback.

    Reads manual_pwm_target_pump_* / manual_pwm_target_fan_* from Redis, applies pump
    clamping (min_duty/max_duty) to protect hardware, writes to PCB registers.
    """
    try:
        wiring = (cfg.get('wiring') or {}).get('pwm') or {}
        pump_chs = wiring.get('pump_ch') or []
        fan_chs = wiring.get('fan_ch') or []
        pump_cfg = cfg.get('pump', {}) or {}
        pump_min_duty = int(pump_cfg.get('min_duty', 0))
        pump_max_duty = int(pump_cfg.get('max_duty', 1000))

        # Pump channels: apply clamping (same protection as apply_initial_state)
        for ch in pump_chs:
            idx = ch - 1
            target_str = rd.get(K.manual_pwm_target_pump(idx))
            if target_str is None:
                continue
            try:
                duty = int(target_str)
            except (ValueError, TypeError):
                log.warning("manual_pwm_target_pump_%d invalid: %s", idx, target_str)
                continue
            # Clamp pump duty to safe voltage range (6-12VDC)
            clamped = 0 if duty <= 0 else max(pump_min_duty, min(pump_max_duty, duty))
            pcb.write_register(pcb_driver.hr_pwm_duty(ch), clamped)

        # Fan channels: no clamping (fans safe at any duty)
        for ch in fan_chs:
            idx = ch - 5
            target_str = rd.get(K.manual_pwm_target_fan(idx))
            if target_str is None:
                continue
            try:
                duty = int(target_str)
            except (ValueError, TypeError):
                log.warning("manual_pwm_target_fan_%d invalid: %s", idx, target_str)
                continue
            if 0 <= duty <= 1000:
                pcb.write_register(pcb_driver.hr_pwm_duty(ch), duty)

        log.debug("manual PWM applied from Redis targets")
    except Exception:
        log.exception("manual PWM apply failed")


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
            log.exception("config reload failed; keeping previous cfg — will retry next cycle")
        return self.controller
