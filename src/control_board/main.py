"""control_board entrypoint — config 로드, Modbus 연결, 초기 상태 적용, 메인 루프."""
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
    """PWM 주파수 (HR 12/13/14) — config.yaml의 pwm_freq 적용."""
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
    """Flash 미저장 항목 (PWM duty, DOUT) 적용."""
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
    """port may be a single string or a list (try in order). Returns connected PCB or None."""
    ports = mb['port'] if isinstance(mb['port'], list) else [mb['port']]
    for port in ports:
        pcb = PCB(port=port, baud=mb['baud'], slave=mb['slave'],
                  timeout=float(mb.get('timeout_seconds', 1.0)))
        if pcb.connect() and pcb.probe():
            return pcb, port
        pcb.close()
    return None, None


def main():
    cfg = load_config()
    log.info("config loaded: %s", CONFIG_PATH)
    log.info("env temp/humid: %s", env_sensors.temp_humid_kind() or 'none')

    mb = cfg['modbus']
    pcb, port = _resolve_pcb(mb)
    if pcb is None:
        log.error("PCB not found on %s @ %d slave %d",
                  mb['port'], mb['baud'], mb['slave'])
        return 1
    log.info("PCB connected on %s @ %d, slave %d", port, mb['baud'], mb['slave'])

    rd = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

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
