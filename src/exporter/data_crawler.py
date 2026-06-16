#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""DLC 통합 sensor collector — 단일 entrypoint, 단일 service.

백엔드 family는 ADS1256 존재 여부로 자동 결정 (pcb_driver.detect_backend):
  - legacy (Gen1~2): ADS1256 직결 → dlc_sensors.poll_coolant
  - pcb (Gen3): 제어보드 Modbus → PCBDriver, 매 cycle health check로 liveness 추적

env(air_temp/humit)·chassis는 Pi 직결이라 양 백엔드 공통·무조건 실행 (Rev_C에서
메인보드 OFF로 PCB가 죽어도 온/습도는 계속 수집됨).
"""
import logging
import os
import time

import redis

import dlc_sensors
import pcb_driver
import redis_keys as K

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-7s %(name)s: %(message)s',
)
log = logging.getLogger('data_crawler')

PCB_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pcb_config.yaml')

rd = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)


def is_host_alive(key, dead_after_sec=5.0):
    ttl_ms = rd.pttl(key)
    return 1 if ttl_ms is not None and ttl_ms > 0 else 0


def _update_comm_state(fails, timeout_n, disconnect_n):
    if fails == 0:
        rd.set(K.COMM_STATUS, 'ok')
    elif fails >= disconnect_n:
        rd.set(K.COMM_STATUS, 'disconnected')
    elif fails >= timeout_n:
        rd.set(K.COMM_STATUS, 'timeout')


def _load_yaml(path):
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    backend = pcb_driver.detect_backend()
    log.info("backend = %s (temp/humid via Pi-side, always-on)", backend)

    driver = None
    reloader = None
    cycle_s = 1.0
    timeout_n = disconnect_n = None
    prev_alive = False
    consecutive_fail = 0

    if backend == 'pcb':
        import pcb_control
        cfg = _load_yaml(PCB_CONFIG_PATH)
        cycle_s = float(cfg.get('loop', {}).get('cycle_seconds', 1.0))
        comm_cfg = cfg.get('comm', {}) or {}
        timeout_n = int(comm_cfg.get('timeout_after_failures', 3))
        disconnect_n = int(comm_cfg.get('disconnected_after_failures', 10))
        driver = pcb_driver.PCBDriver(cfg)
        reloader = pcb_control.ConfigReloader(PCB_CONFIG_PATH, cfg)
        log.info("PCB collector @ %.2fs cadence (liveness via 1Hz health check)", cycle_s)

    try:
        while True:
            t0 = time.monotonic()

            if backend == 'pcb':
                controller = reloader.maybe_reload(driver)
                alive = driver.health_check()
                if alive:
                    if not prev_alive:
                        log.info("PCB alive — applying initial state")
                        driver.on_connect(rd)
                    ok = False
                    try:
                        ok = driver.poll(rd)
                    except Exception:
                        log.exception("driver.poll raised")
                    consecutive_fail = 0 if ok else consecutive_fail + 1
                    if ok:
                        try:
                            controller.update(driver, rd)
                        except Exception:
                            log.exception("controller.update failed")
                else:
                    consecutive_fail += 1
                prev_alive = alive
                rd.set(K.COMM_CONSECUTIVE_FAILURES, consecutive_fail)
                _update_comm_state(consecutive_fail, timeout_n, disconnect_n)
            else:
                try:
                    dlc_sensors.poll_coolant(rd)
                except Exception:
                    log.exception("poll_coolant failed")

            # ── env / chassis — 양 백엔드 공통, 무조건 (Pi-side 상시) ──
            try:
                dlc_sensors.update_env(rd)
                dlc_sensors.update_chassis(rd)
            except Exception:
                log.exception("env/chassis update failed")

            rd.set(K.HOST_STAT, str(is_host_alive("host_ttl", 5.0)))

            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, cycle_s - elapsed))
    except KeyboardInterrupt:
        log.info("interrupted")
    finally:
        if driver is not None:
            driver.close()


if __name__ == '__main__':
    main()
