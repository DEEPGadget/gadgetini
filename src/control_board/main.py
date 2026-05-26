"""control_board entrypoint - load config, connect Modbus, apply initial state, run main loop."""
import logging
import os
import sys

import yaml
import redis

from . import registers as R
from . import env_sensors
from .modbus_client import PCB
from .controller import FanCurveController
from .main_loop import run


CONFIG_PATH = os.environ.get(
    'CONTROL_BOARD_CONFIG',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml'),
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-7s %(name)s: %(message)s',
)
log = logging.getLogger('control_board')


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def apply_pwm_freq(pcb, cfg):
    """Apply PWM frequencies (HR 12/13/14) from the pwm_freq section of config.yaml."""
    freq = cfg.get('pwm_freq') or {}
    mapping = [
        (R.HR_PWM_FREQ_TIM1, 'tim1'),
        (R.HR_PWM_FREQ_TIM2, 'tim2'),
        (R.HR_PWM_FREQ_TIM8, 'tim8'),
    ]
    applied = {}
    for hr, key in mapping:
        v = freq.get(key)
        if v is None:
            continue
        pcb.write_register(hr, int(v))
        applied[key] = int(v)
    log.info("PWM freq applied: %s", applied or 'none (config missing pwm_freq)')


def apply_initial_state(pcb, cfg):
    """Apply non-Flash items (PWM duty, DOUT)."""
    duty_cfg = cfg.get('initial_pwm_duty', {})
    pump = duty_cfg.get('pump') or {}
    fan = duty_cfg.get('fan') or {}

    for ch in range(1, 5):
        v = int(pump.get(f'ch{ch}', 0))
        pcb.write_register(R.hr_pwm_duty(ch), v)
    for ch in range(5, 13):
        v = int(fan.get(f'ch{ch}', 0))
        pcb.write_register(R.hr_pwm_duty(ch), v)

    dout = int(cfg.get('initial_dout_bitmask', 0))
    pcb.write_register(R.HR_DOUT_BITMASK, dout)
    log.info("initial PWM duty + DOUT applied")


def _resolve_pcb(mb):
    """port/baud may be single value or list (try in order). Returns connected PCB or None."""
    ports = mb['port'] if isinstance(mb['port'], list) else [mb['port']]
    bauds = mb['baud'] if isinstance(mb['baud'], list) else [mb['baud']]
    for port in ports:
        for baud in bauds:
            pcb = PCB(port=port, baud=int(baud), slave=mb['slave'],
                      timeout=float(mb.get('timeout_seconds', 1.0)))
            if pcb.connect() and pcb.probe():
                return pcb, port, int(baud)
            pcb.close()
    return None, None, None


def main():
    cfg = load_config()
    log.info("config loaded: %s", CONFIG_PATH)
    log.info("env temp/humid: %s", env_sensors.temp_humid_kind() or 'none')

    mb = cfg['modbus']
    pcb, port, baud = _resolve_pcb(mb)
    if pcb is None:
        log.error("PCB not found on %s @ %s slave %d",
                  mb['port'], mb['baud'], mb['slave'])
        return 1
    log.info("PCB connected on %s @ %d, slave %d", port, baud, mb['slave'])

    rd = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

    # Explicitly initialize comm state right after a successful PCB probe - prevents
    # the UI from showing a stale 'disconnected'/'timeout' red left over from a previous run.
    # If polling actually fails, main_loop._update_comm_state will transition normally.
    from . import redis_keys as K
    rd.set(K.COMM_STATUS, 'ok')
    rd.set(K.COMM_CONSECUTIVE_FAILURES, 0)

    apply_pwm_freq(pcb, cfg)
    apply_initial_state(pcb, cfg)

    fan_chs = (cfg.get('wiring', {}).get('pwm') or {}).get('fan_ch') or []
    controller = FanCurveController(cfg['fan_curve'], fan_chs)

    log.info("entering main loop @ %.2f s cadence", cfg['loop']['cycle_seconds'])
    try:
        run(pcb, rd, cfg, controller, CONFIG_PATH)
    except KeyboardInterrupt:
        log.info("interrupted")
    finally:
        pcb.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
