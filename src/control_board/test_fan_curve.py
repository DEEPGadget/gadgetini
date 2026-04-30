#!/usr/bin/env python3
"""Fake-data scenario test for FanCurveController.

control_board.service를 잠시 멈추고, Redis의 coolant_temp_outlet1 값을
시나리오대로 주입하면서 controller.update()가 PCB HR(팬 PWM duty)에
올바른 값을 쓰는지 확인한다. 실제 controller / config / PCB 모두 production
경로 그대로 사용.
"""
import os
import sys
import time

# repo의 src/ 디렉토리를 import path에 (control_board 패키지로 인식되도록)
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

    # PCB 연결 (port 리스트 fallback)
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

    # 시나리오: 상승 → 정점 → 하강 → 경계 hysteresis 테스트
    scenarios = [
        ('초기 idle',        25.0),
        ('상승 → 30°C 직전', 29.9),
        ('상승 → stage 2',   30.5),
        ('상승 → stage 3',   45.0),
        ('상승 → stage 4',   55.0),
        ('상승 → max',       62.0),
        ('하강 → stage 4',   58.0),
        ('hysteresis 50→ 49', 49.0),    # 50 boundary - hyst(1) = 49 — stage 4 유지 가능
        ('hysteresis 48.9',  48.9),     # boundary - hyst 미만 → stage 3
        ('하강 → stage 2',   35.0),
        ('하강 → idle',      25.0),
    ]

    stages = cfg['fan_curve']['stages']
    hyst = cfg['fan_curve'].get('hysteresis_c', 1.0)
    last_idx = None
    pass_count = 0
    fail_count = 0

    ch_hdr = "  ".join(f"CH{ch:>2}" for ch in fan_chs)
    print(f"\n{'시나리오':<22}{'temp':>6}{'  exp_idx':>10}{'exp_duty':>10}  {ch_hdr}  {'결과'}")
    print('─' * 80)
    for label, temp in scenarios:
        rd.set(K.COOLANT_TEMP_OUTLET1, temp)
        controller.update(pcb, rd)
        time.sleep(0.3)   # PCB write 반영 대기
        # wiring 의 fan_chs 각 채널 duty 개별 readback
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
    print(f"\n결과: {pass_count} pass, {fail_count} fail")

    # cleanup — duty 0으로 복귀
    for ch in fan_chs:
        pcb.write_register(R.hr_pwm_duty(ch), 0)
    rd.delete(K.COOLANT_TEMP_OUTLET1)
    pcb.close()
    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
