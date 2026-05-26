"""Fan duty control - linear interpolation between outlet temperature and duty.

Below `min_temp`: idle at `min_duty` (silent baseline).
Above `max_temp`: `max_duty` (usually 1000 = 100%).
In between: linear interpolation. No stage chattering, so hysteresis is unnecessary.

To avoid Modbus chatter, only write when the change exceeds `_WRITE_DEADBAND` (0.1% units).
Pump duty is never changed (kept fixed at the initial value from config.yaml).
"""
import logging

from . import registers as R
from . import redis_keys as K

log = logging.getLogger(__name__)

# Skip modbus write if duty change is below this value - avoids per-cycle writes from 0.1 °C noise.
_WRITE_DEADBAND = 5  # 0.5%


def _contiguous_runs(channels):
    """Group consecutive channels: [8,9,10,12] → [(8, [8,9,10]), (12, [12])]."""
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
        self.min_temp = float(cfg.get('min_temp', 30))
        self.max_temp = float(cfg.get('max_temp', 60))
        self.min_duty = int(cfg.get('min_duty', 100))
        self.max_duty = int(cfg.get('max_duty', 1000))
        if self.max_temp <= self.min_temp:
            # degenerate — fall back to hard step at min_temp
            self.max_temp = self.min_temp + 1.0
        self.fan_chs = list(fan_pwm_chs or [])
        # Consecutive channels are grouped into a single FC16 transaction for atomic writes -
        # avoids firmware/timing issues that can occur when updating two channels via back-to-back FC06.
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
        """Read outlet1 → compute duty → write to all configured fan channels."""
        if not self.fan_chs:
            return
        v = rd.get(K.COOLANT_TEMP_OUTLET1)
        if v is None:
            log.warning("no %s — fan duty unchanged", K.COOLANT_TEMP_OUTLET1)
            return
        try:
            temp_c = float(v)
        except (TypeError, ValueError):
            return
        duty = self._compute_duty(temp_c)
        # write-deadband: skip the modbus call if the change from the last written value is small
        if self._last_written is not None and abs(duty - self._last_written) < _WRITE_DEADBAND:
            # Exception: if we just reached min/max but the previous value was not at the limit,
            # guarantee one write for clamp accuracy.
            if duty in (self.min_duty, self.max_duty) and self._last_written != duty:
                pass
            else:
                return
        for first_ch, run in self._runs:
            base_hr = R.hr_pwm_duty(first_ch)
            if len(run) == 1:
                ok = pcb.write_register(base_hr, duty)
            else:
                ok = pcb.write_registers(base_hr, [duty] * len(run))
            if not ok:
                log.warning("fan duty write failed: CH %s (HR %d, %d ch) duty=%d",
                            run, base_hr, len(run), duty)
        self._last_written = duty
        log.debug("outlet=%.1f °C → duty=%d → CH %s", temp_c, duty, self.fan_chs)
