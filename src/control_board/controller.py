"""Fan duty 제어 — outlet 온도 lookup + ±1 °C hysteresis.

펌프 duty는 변경하지 않는다 (config.yaml 초기값 그대로 고정 운용).
"""
import logging

from . import registers as R
from . import redis_keys as K

log = logging.getLogger(__name__)


def _contiguous_runs(channels):
    """[8,9,10,12] → [(8, [8,9,10]), (12, [12])] 같이 연속 채널을 묶어 반환."""
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
    """Stage 1 lookup. self._last_idx로 단계 간 chattering 방지."""

    def __init__(self, fan_curve_cfg, fan_pwm_chs):
        self.stages = list(fan_curve_cfg['stages'])
        self.hyst = float(fan_curve_cfg.get('hysteresis_c', 1.0))
        self.fan_chs = list(fan_pwm_chs or [])
        # 연속 채널은 FC16 한 트랜잭션으로 묶어 atomic write — back-to-back FC06로
        # 두 채널 갱신 시 발생할 수 있는 펌웨어/타이밍 이슈 회피.
        self._runs = _contiguous_runs(self.fan_chs)
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
        for first_ch, run in self._runs:
            base_hr = R.hr_pwm_duty(first_ch)
            if len(run) == 1:
                ok = pcb.write_register(base_hr, duty)
            else:
                ok = pcb.write_registers(base_hr, [duty] * len(run))
            if not ok:
                log.warning("fan duty write failed: CH %s (HR %d, %d ch) duty=%d",
                            run, base_hr, len(run), duty)
        log.debug("outlet=%.1f °C → stage[%d] duty=%d → CH %s",
                  temp_c, idx, duty, self.fan_chs)
