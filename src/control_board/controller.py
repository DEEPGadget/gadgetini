"""Fan duty 제어 — outlet 온도 lookup + ±1 °C hysteresis.

펌프 duty는 변경하지 않는다 (config.yaml 초기값 그대로 고정 운용).
"""
import logging

from . import registers as R
from . import redis_keys as K

log = logging.getLogger(__name__)


class FanCurveController:
    """Stage 1 lookup. self._last_idx로 단계 간 chattering 방지."""

    def __init__(self, fan_curve_cfg, fan_pwm_chs):
        self.stages = list(fan_curve_cfg['stages'])
        self.hyst = float(fan_curve_cfg.get('hysteresis_c', 1.0))
        self.fan_chs = list(fan_pwm_chs or [])
        self._last_idx = None

    def _select_stage_idx(self, temp_c):
        """Return stage index for given temperature, applying ±hyst hysteresis."""
        # Forward selection — first stage whose until_outlet > temp wins; null = ceiling
        idx = len(self.stages) - 1
        for i, st in enumerate(self.stages):
            until = st.get('until_outlet')
            if until is not None and temp_c < until:
                idx = i
                break

        # Hysteresis: only step *down* (lower stage) if we're hyst below the previous boundary.
        if self._last_idx is not None and idx < self._last_idx:
            prev_boundary = self.stages[idx].get('until_outlet')
            if prev_boundary is not None and temp_c >= prev_boundary - self.hyst:
                idx = self._last_idx

        self._last_idx = idx
        return idx

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
        idx = self._select_stage_idx(temp_c)
        duty = int(self.stages[idx]['duty'])
        for ch in self.fan_chs:
            pcb.write_register(R.hr_pwm_duty(ch), duty)
        log.debug("outlet=%.1f °C → stage[%d] duty=%d → CH %s", temp_c, idx, duty, self.fan_chs)
