"""PCB 냉각 정책 — fan duty 제어 + config 핫리로드.

Fan duty: outlet1 온도 ↔ duty linear interpolation.
  min_temp 이하 → min_duty (silent baseline, 영구 회전).
  max_temp 이상 → max_duty (보통 1000 = 100%).
  그 사이 선형 보간. 단계 chattering 없어 hysteresis 불필요.
펌프 duty는 고정 (pcb_config.yaml initial_pwm_duty 그대로) — 유량 센서 없음.
STANDBY/ACTIVE 상태 머신 없음 (12V 하드웨어 인터록이 그 역할).

config 핫리로드: pcb_config.yaml mtime 변화 시 fan_curve / pump duty / DOUT 런타임 반영
(web UI 편집 → REST API → 파일 write → 다음 cycle 픽업).
"""
import logging
import os

import yaml

import pcb_driver
import redis_keys as K

log = logging.getLogger('pcb_control')

# duty 변화가 이 값 미만이면 modbus write skip — 0.1°C 노이즈에 매 cycle write 회피.
_WRITE_DEADBAND = 5  # 0.5%


def _contiguous_runs(channels):
    """[8,9,10,12] → [(8,[8,9,10]), (12,[12])] — 연속 채널 묶기."""
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
        # 연속 채널은 FC16 한 트랜잭션으로 atomic write.
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
        # write-deadband: 직전 쓴 값과 차이가 작으면 skip (단, min/max 끝값 도달은 1회 보장)
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
        log.debug("outlet=%.1f °C → duty=%d → CH %s", temp_c, duty, self.fan_chs)


def _fan_chs(cfg):
    return (cfg.get('wiring', {}).get('pwm') or {}).get('fan_ch') or []


def make_controller(cfg):
    return FanCurveController(cfg.get('fan_curve', {}), _fan_chs(cfg))


class ConfigReloader:
    """pcb_config.yaml mtime watch — 변경 시 cfg/controller 갱신.

    펌프 duty 또는 DOUT bitmask가 바뀐 경우에만 PCB에 재write (매 cycle write 회피;
    fan duty는 controller가 어차피 갱신). Reload 실패 시 기존 유지하고 죽지 않음.
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
        """변경 감지 시 cfg/controller 갱신하고 driver에 반영. 항상 현재 controller 반환."""
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
            self.last_mtime = m   # 같은 깨진 파일 매 cycle 재시도 방지
        return self.controller
