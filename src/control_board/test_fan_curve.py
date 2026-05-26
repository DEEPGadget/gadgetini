#!/usr/bin/env python3
"""Fake-data scenario test for FanCurveController.

Stop control_board.service briefly, inject scenario values into the Redis
coolant_temp_outlet1 key, call controller.update(), and verify that the correct
value is written to the PCB HR (fan PWM duty). Uses the real controller / config /
PCB through the production code path.
"""
import os
import sys
import time

# Put the repo's src/ directory on the import path (so control_board resolves as a package)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
import redis
from control_board.modbus_client import PCB
from control_board.controller import FanCurveController
from control_board import registers as R
from control_board import redis_keys as K

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')


def expected_duty(stages, hyst, last_idx, temp_c):
    """Replay controller logic for sanity-check expected output."""
    idx = len(stages) - 1
    for i, st in enumerate(stages):
        until = st.get('until_outlet')
        if until is not None and temp_c < until:
            idx = i
            break
    if last_idx is not None and idx < last_idx:
        prev_boundary = stages[idx].get('until_outlet')
        if prev_boundary is not None and temp_c >= prev_boundary - hyst:
            idx = last_idx
    return idx, stages[idx]['duty']


def main():
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)

    # PCB connect (with port list fallback)
    mb = cfg['modbus']
    ports = mb['port'] if isinstance(mb['port'], list) else [mb['port']]
    pcb = None
    for port in ports:
        p = PCB(port=port, baud=mb['baud'], slave=mb['slave'],
                timeout=float(mb.get('timeout_seconds', 1.0)))
        if p.connect() and p.probe():
            pcb = p
            print(f"PCB connected on {port}")
            break
        p.close()
    if pcb is None:
        print("ERR: PCB not reachable. Stop control_board.service first.")
        return 1

    rd = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

    fan_chs = cfg['wiring']['pwm']['fan_ch']
    controller = FanCurveController(cfg['fan_curve'], fan_chs)

    # Scenarios: ramp up → peak → ramp down → boundary hysteresis test
    scenarios = [
        ('initial idle',      25.0),
        ('ramp up, just below 30°C', 29.9),
        ('ramp up → stage 2', 30.5),
        ('ramp up → stage 3', 45.0),
        ('ramp up → stage 4', 55.0),
        ('ramp up → max',    62.0),
        ('ramp down → stage 4', 58.0),
        ('hysteresis 50 → 49', 49.0),  # 50 boundary - hyst(1) = 49 → stage 4 may hold
        ('hysteresis 48.9',   48.9),    # below boundary - hyst → stage 3
        ('ramp down → stage 2', 35.0),
        ('ramp down → idle', 25.0),
    ]

    stages = cfg['fan_curve']['stages']
    hyst = cfg['fan_curve'].get('hysteresis_c', 1.0)
    last_idx = None
    pass_count = 0
    fail_count = 0

    ch_hdr = "  ".join(f"CH{ch:>2}" for ch in fan_chs)
    print(f"\n{'scenario':<22}{'temp':>6}{'  exp_idx':>10}{'exp_duty':>10}  {ch_hdr}  {'result'}")
    print('─' * 80)
    for label, temp in scenarios:
        rd.set(K.COOLANT_TEMP_OUTLET1, temp)
        controller.update(pcb, rd)
        time.sleep(0.3)   # wait for PCB write to settle
        # Individually readback the duty of each fan_chs channel from wiring
        readbacks = []
        for ch in fan_chs:
            rb = pcb.read_holding_registers(R.hr_pwm_duty(ch), 1)
            readbacks.append(rb[0] if rb else None)

        exp_idx, exp_duty = expected_duty(stages, hyst, last_idx, temp)
        last_idx = exp_idx
        ok = all(rb == exp_duty for rb in readbacks)
        mark = '✓' if ok else '✗'
        if ok: pass_count += 1
        else:  fail_count += 1
        rb_str = "  ".join(f"{rb if rb is not None else '?':>4}" for rb in readbacks)
        print(f"{label:<22}{temp:>6.1f}{exp_idx:>10}{exp_duty:>10}  {rb_str}  {mark}")

    print('─' * 80)
    print(f"\nresult: {pass_count} pass, {fail_count} fail")

    # cleanup - restore duty to 0
    for ch in fan_chs:
        pcb.write_register(R.hr_pwm_duty(ch), 0)
    rd.delete(K.COOLANT_TEMP_OUTLET1)
    pcb.close()
    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
