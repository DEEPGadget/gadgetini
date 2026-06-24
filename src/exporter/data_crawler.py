#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Unified DLC sensor collector — single entrypoint, single service.

Backend is chosen by ADS1256 presence (pcb_driver.detect_backend):
  legacy = ADS1256 direct (poll_coolant); pcb = control board Modbus (PCBDriver,
  liveness tracked by a per-cycle health check).

Air temp/humidity and chassis come from Pi-attached sensors, so they run on both
backends unconditionally — they keep collecting even when the PCB is powered down.
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


# host writes `host_ttl` with EXPIRE 7 each cycle; key presence = host telemetry
# is arriving (catches host-script crashes a link check would miss).
HOST_TTL_KEY = 'host_ttl'


def is_host_alive():
    try:
        return 1 if rd.exists(HOST_TTL_KEY) else 0
    except redis.RedisError:
        return 0


def _store_pump_pwm_to_redis(rd, cfg):
    """Store pump PWM (from config) in Redis for Web UI readback."""
    try:
        pump_cfg = (cfg.get('initial_pwm_duty') or {}).get('pump') or {}
        wiring = (cfg.get('wiring') or {}).get('pwm') or {}
        pump_chs = wiring.get('pump_ch') or []

        for i, ch in enumerate(pump_chs):
            # config keys are 'ch1'..'ch4' (strings); index by physical channel
            duty = pump_cfg.get(f"ch{ch}")
            if duty is None:
                continue
            duty = int(duty)
            if 0 <= duty <= 1000:
                rd.set(f"pwm_duty_pump_{i}", duty)
        log.debug("pump PWM stored to Redis: %s", pump_cfg)
    except Exception:
        log.exception("failed to store pump PWM to Redis")


def _apply_manual_pwm(driver, rd):
    """Apply manual PWM from config (channel write) — no temperature feedback."""
    try:
        import yaml
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pcb_config.yaml')
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f) or {}
        manual_cfg = cfg.get('manual_pwm') or {}
        pump_duties = manual_cfg.get('pump') or []
        fan_duties = manual_cfg.get('fan') or []

        wiring = (cfg.get('wiring') or {}).get('pwm') or {}
        pump_chs = wiring.get('pump_ch') or []
        fan_chs = wiring.get('fan_ch') or []

        # manual_pwm arrays are in PHYSICAL channel order (pump=CH1~4, fan=CH5~12),
        # matching the Web UI sliders — index by channel offset, not by wiring slot.
        for ch in pump_chs:
            idx = ch - 1
            if 0 <= idx < len(pump_duties) and pump_duties[idx] is not None:
                duty = int(pump_duties[idx])
                if 0 <= duty <= 1000:
                    driver.write_register(pcb_driver.hr_pwm_duty(ch), duty)

        for ch in fan_chs:
            idx = ch - 5
            if 0 <= idx < len(fan_duties) and fan_duties[idx] is not None:
                duty = int(fan_duties[idx])
                if 0 <= duty <= 1000:
                    driver.write_register(pcb_driver.hr_pwm_duty(ch), duty)

        log.debug("manual PWM applied: pump=%s fan=%s", pump_duties, fan_duties)
    except Exception:
        log.exception("manual PWM apply failed")


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
                        # Store pump PWM in Redis for Web UI
                        _store_pump_pwm_to_redis(rd, reloader.cfg)
                    ok = False
                    try:
                        ok = driver.poll(rd)
                    except Exception:
                        log.exception("driver.poll raised")
                    consecutive_fail = 0 if ok else consecutive_fail + 1
                    if ok:
                        try:
                            # Check control_mode: manual or auto (default)
                            control_mode = rd.get('control_mode') or 'auto'
                            if control_mode == 'manual':
                                _apply_manual_pwm(driver, rd)
                            else:
                                controller.update(driver, rd)
                        except Exception:
                            log.exception("control update failed")
                else:
                    consecutive_fail += 1   # PCB down (mainboard off / cycling)
                prev_alive = alive
                rd.set(K.COMM_CONSECUTIVE_FAILURES, consecutive_fail)
                _update_comm_state(consecutive_fail, timeout_n, disconnect_n)
            else:
                try:
                    dlc_sensors.poll_coolant(rd)
                except Exception:
                    log.exception("poll_coolant failed")

            # Pi-attached env/chassis — both backends, always (independent of PCB)
            try:
                dlc_sensors.update_env(rd)
                dlc_sensors.update_chassis(rd)
            except Exception:
                log.exception("env/chassis update failed")

            rd.set(K.HOST_STAT, str(is_host_alive()))

            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, cycle_s - elapsed))
    except KeyboardInterrupt:
        log.info("interrupted")
    finally:
        if driver is not None:
            driver.close()


if __name__ == '__main__':
    main()
