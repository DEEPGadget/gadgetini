"""Main loop - polling → environment sensors → controller.

Single-threaded, sequential execution over a single Modbus serial bus.
Threshold alarms are evaluated as raw metrics by Prometheus alert rules + Grafana.
When config.yaml mtime changes, the loop auto-reloads and picks up fan_curve / pump duty /
DOUT changes at runtime (web UI edit → REST API → file write → picked up next cycle).
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

        # === 0. config.yaml mtime watch - reload on change ===
        cfg, controller, last_mtime, last_pump_duties, last_dout = _maybe_reload(
            pcb, cfg, controller, config_path,
            last_mtime, last_pump_duties, last_dout,
        )

        # === 1. PCB polling ===
        ok = False
        try:
            ok = polling.poll_once(pcb, rd, cfg)
        except Exception:
            log.exception("polling.poll_once raised")

        if ok:
            if consecutive_fail > 0:
                log.info("PCB poll recovered after %d consecutive failures — re-applying initial state",
                         consecutive_fail)
                # PCB power may have been cycled - non-Flash items (PWM duty, DOUT) could have
                # been reset to firmware defaults, so re-apply them from config.
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

        # === 2. Environment sensors (not via Modbus) ===
        try:
            t = env_sensors.get_air_temp()
            if t is not None:
                rd.set(K.AIR_TEMP, round(t, 1))
            h = env_sensors.get_air_humit()
            if h is not None:
                rd.set(K.AIR_HUMIT, round(h, 1))
            # MPU6050 - dg5w only; dg5r returns None so the SET is skipped
            stabil = env_sensors.get_chassis_stabil()
            if stabil is not None:
                rd.set(K.CHASSIS_STABIL, stabil)
        except Exception:
            log.exception("env_sensors read failed")

        # === 3. Controller (update fan duty) ===
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
    """Refresh cfg/controller when config.yaml mtime changes.

    Only writes back to the PCB when pump duty or the DOUT bitmask actually changed
    (avoid per-cycle writes - fan duty is updated by the controller anyway).
    On reload failure, keep the previous cfg/controller and don't kill the service.
    """
    m = _safe_mtime(config_path)
    if m is None or m == last_mtime:
        return cfg, controller, last_mtime, last_pump_duties, last_dout

    try:
        # Lazy import to avoid a hard dependency on the main module
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
        # Bump mtime so we don't keep retrying the same broken file every cycle
        return cfg, controller, m, last_pump_duties, last_dout
