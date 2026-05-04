"""메인 루프 — Polling → 환경 센서 → Controller.

단일 쓰레드, Modbus 단일 시리얼 버스 순차 실행.
임계 알람은 Prometheus alert rule + Grafana 측에서 raw metric으로 평가.
config.yaml mtime이 바뀌면 자동 reload하여 fan_curve / 펌프 duty / DOUT 변경분을
런타임 반영한다 (web UI 편집 → REST API → 파일 write → 다음 cycle에 픽업).
"""
import logging
import os
import time

from . import polling
from . import env_sensors
from . import redis_keys as K
from .controller import FanCurveController

log = logging.getLogger(__name__)


def run(pcb, rd, cfg, controller, config_path):
    """Run forever until KeyboardInterrupt or systemd SIGTERM."""
    cycle = float(cfg['loop']['cycle_seconds'])
    comm_cfg = cfg['comm']
    timeout_n = int(comm_cfg['timeout_after_failures'])
    disconnect_n = int(comm_cfg['disconnected_after_failures'])

    consecutive_fail = 0
    last_mtime = _safe_mtime(config_path)
    last_pump_duties = _extract_pump_duties(cfg)
    last_dout = int(cfg.get('initial_dout_bitmask', 0))

    while True:
        t0 = time.monotonic()

        # ── 0. config.yaml mtime watch — 변경 시 reload ──
        cfg, controller, last_mtime, last_pump_duties, last_dout = _maybe_reload(
            pcb, cfg, controller, config_path,
            last_mtime, last_pump_duties, last_dout,
        )

        # ── 1. PCB polling ──
        ok = False
        try:
            ok = polling.poll_once(pcb, rd, cfg)
        except Exception:
            log.exception("polling.poll_once raised")

        if ok:
            if consecutive_fail > 0:
                log.info("PCB poll recovered after %d consecutive failures — re-applying initial state",
                         consecutive_fail)
                # PCB 전원이 끊겼다 들어왔을 가능성 — Flash 미저장 항목(PWM duty, DOUT)이
                # 펌웨어 기본값으로 리셋됐을 수 있으므로 config 기준으로 다시 적용한다.
                try:
                    from .main import apply_initial_state
                    apply_initial_state(pcb, cfg)
                except Exception:
                    log.exception("re-apply initial state after recovery failed")
            consecutive_fail = 0
        else:
            consecutive_fail += 1
            log.warning("PCB poll failed (consecutive %d)", consecutive_fail)

        rd.set(K.COMM_CONSECUTIVE_FAILURES, consecutive_fail)
        _update_comm_state(rd, consecutive_fail, timeout_n, disconnect_n)

        # ── 2. 환경 센서 (aiexpo 행사용 dummy — 실제 센서 미사용) ──
        try:
            t = env_sensors.get_air_temp_dummy(rd)
            if t is not None:
                rd.set(K.AIR_TEMP, round(t, 1))
            h = env_sensors.get_air_humit_dummy(rd)
            if h is not None:
                rd.set(K.AIR_HUMIT, round(h, 1))
            # MPU6050 — dg5w 한정, dg5r은 None 반환하므로 SET 생략
            stabil = env_sensors.get_chassis_stabil()
            if stabil is not None:
                rd.set(K.CHASSIS_STABIL, stabil)
        except Exception:
            log.exception("env_sensors read failed")

        # ── 3. Controller (fan duty 갱신) ──
        if ok:
            try:
                controller.update(pcb, rd)
            except Exception:
                log.exception("controller.update failed")

        elapsed = time.monotonic() - t0
        time.sleep(max(0.0, cycle - elapsed))


def _update_comm_state(rd, fails, timeout_n, disconnect_n):
    if fails == 0:
        rd.set(K.COMM_STATUS, 'ok')
    elif fails >= disconnect_n:
        rd.set(K.COMM_STATUS, 'disconnected')
    elif fails >= timeout_n:
        rd.set(K.COMM_STATUS, 'timeout')


def _safe_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _extract_pump_duties(cfg):
    pump = (cfg.get('initial_pwm_duty', {}) or {}).get('pump') or {}
    return {k: int(v) for k, v in pump.items()}


def _maybe_reload(pcb, cfg, controller, config_path,
                  last_mtime, last_pump_duties, last_dout):
    """config.yaml mtime 비교 후 변경 시 cfg/controller 갱신.

    펌프 duty 또는 DOUT bitmask가 바뀐 경우에만 PCB에 다시 write
    (매 cycle write 회피 — fan duty는 controller가 어차피 갱신함).
    Reload 실패 시 기존 cfg/controller 유지하고 서비스 안 죽음.
    """
    m = _safe_mtime(config_path)
    if m is None or m == last_mtime:
        return cfg, controller, last_mtime, last_pump_duties, last_dout

    try:
        # main 모듈 의존성 회피를 위해 lazy import
        from .main import load_config, apply_initial_state

        new_cfg = load_config()
        fan_chs = (new_cfg.get('wiring', {}).get('pwm') or {}).get('fan_ch') or []
        new_controller = FanCurveController(new_cfg['fan_curve'], fan_chs)

        new_pump = _extract_pump_duties(new_cfg)
        new_dout = int(new_cfg.get('initial_dout_bitmask', 0))
        if new_pump != last_pump_duties or new_dout != last_dout:
            apply_initial_state(pcb, new_cfg)
            last_pump_duties = new_pump
            last_dout = new_dout

        log.info("config.yaml reloaded (mtime change)")
        return new_cfg, new_controller, m, last_pump_duties, last_dout
    except Exception:
        log.exception("config reload failed; keeping previous cfg")
        # mtime은 갱신해서 같은 깨진 파일을 매 cycle 재시도하지 않도록
        return cfg, controller, m, last_pump_duties, last_dout
