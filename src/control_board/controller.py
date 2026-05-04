"""Fan duty 제어 — outlet 온도 ↔ duty linear interpolation.

`min_temp` 이하: `min_duty` 로 idle (silent baseline).
`max_temp` 이상: `max_duty` (보통 1000 = 100%).
그 사이: 선형 보간. 단계 chattering 이 없어 hysteresis 불필요.

Modbus chatter 회피를 위해 `_WRITE_DEADBAND` (0.1% 단위) 이상 변할 때만 write.
펌프 duty는 변경하지 않는다 (config.yaml 초기값 그대로 고정 운용).
"""
import logging

from . import registers as R
from . import redis_keys as K

log = logging.getLogger(__name__)

# duty 변화가 이 값 미만이면 modbus write skip — 0.1°C 노이즈에 매 cycle write 회피.
_WRITE_DEADBAND = 5  # 0.5%


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
        # 연속 채널은 FC16 한 트랜잭션으로 묶어 atomic write — back-to-back FC06로
        # 두 채널 갱신 시 발생할 수 있는 펌웨어/타이밍 이슈 회피.
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
        # write-deadband: 마지막 쓴 값과 차이가 작으면 modbus 호출 skip
        if self._last_written is not None and abs(duty - self._last_written) < _WRITE_DEADBAND:
            # 단, 양 끝(min/max)에 도달했는데 직전 값이 끝값이 아니면 한 번은 보장 — clamp 정확도
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
