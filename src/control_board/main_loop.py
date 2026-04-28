"""메인 루프 — Polling → 환경 센서 → Controller → Alarm.

단일 쓰레드, Modbus 단일 시리얼 버스 순차 실행.
"""
import logging
import time

from . import polling
from . import env_sensors
from . import alarm_checker
from . import redis_keys as K

log = logging.getLogger(__name__)


def run(pcb, rd, cfg, controller):
    """Run forever until KeyboardInterrupt or systemd SIGTERM."""
    cycle = float(cfg['loop']['cycle_seconds'])
    comm_cfg = cfg['thresholds']['comm']
    timeout_n = int(comm_cfg['timeout_after_failures'])
    disconnect_n = int(comm_cfg['disconnected_after_failures'])

    consecutive_fail = 0

    while True:
        t0 = time.monotonic()

        # ── 1. PCB polling ──
        ok = False
        try:
            ok = polling.poll_once(pcb, rd, cfg.get('wiring', {}))
        except Exception:
            log.exception("polling.poll_once raised")

        if ok:
            if consecutive_fail > 0:
                log.info("PCB poll recovered after %d consecutive failures", consecutive_fail)
            consecutive_fail = 0
        else:
            consecutive_fail += 1
            log.warning("PCB poll failed (consecutive %d)", consecutive_fail)

        rd.set(K.COMM_CONSECUTIVE_FAILURES, consecutive_fail)
        _update_comm_state(rd, consecutive_fail, timeout_n, disconnect_n)

        # ── 2. 환경 센서 (Modbus 미경유) ──
        try:
            t = env_sensors.get_air_temp()
            if t is not None:
                rd.set(K.AIR_TEMP, round(t, 1))
            h = env_sensors.get_air_humit()
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

        # ── 4. Alarm threshold check ──
        try:
            alarm_checker.check_all(rd, cfg['thresholds'])
        except Exception:
            log.exception("alarm_checker.check_all failed")

        elapsed = time.monotonic() - t0
        time.sleep(max(0.0, cycle - elapsed))


def _update_comm_state(rd, fails, timeout_n, disconnect_n):
    if fails == 0:
        rd.set(K.COMM_STATUS, 'ok')
        rd.delete(K.alarm('comm_timeout'))
        rd.delete(K.alarm('comm_disconnected'))
    elif fails >= disconnect_n:
        rd.set(K.COMM_STATUS, 'disconnected')
        rd.set(K.alarm('comm_disconnected'), 1)
    elif fails >= timeout_n:
        rd.set(K.COMM_STATUS, 'timeout')
        rd.set(K.alarm('comm_timeout'), 1)
