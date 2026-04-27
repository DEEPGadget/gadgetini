#!/usr/bin/env python3
"""Quick PMP-500 pump probe via PCB TIM1 voltage-control channel.

Steps the pump through a sequence of duties, reads back duty + Tach pulse
frequency at each step, and always returns to 0 at exit (even on interrupt).

Usage:
    python3 probe_pump.py                       # CH1 (HR0), Tach=IR13
    python3 probe_pump.py --ch 2 --tach 14
    python3 probe_pump.py --steps 300,600,900,600,300 --dwell 3
"""
import argparse
import sys
import time
from pymodbus.client import ModbusSerialClient

HR_PWM_DUTY_BASE = 0
IR_SYSTEM_TIMER = 0
IR_PULSE_FREQ_BASE = 13   # CH1~12 → IR 13~24


def read_status(cli, slave, hr_duty, ir_tach):
    duty = cli.read_holding_registers(hr_duty, count=1, device_id=slave).registers[0]
    tach = cli.read_input_registers(ir_tach, count=1, device_id=slave).registers[0]
    return duty, tach


def duty_to_voltage(duty_raw):
    """Manual §10.1: 5%~100% duty → 6~12 V DC (linear)."""
    pct = duty_raw / 10.0
    if pct < 5:
        return 0.0
    return 6.0 + (pct - 5) * 6.0 / 95.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default='/dev/ttyUSB0')
    ap.add_argument('--baud', type=int, default=115200)
    ap.add_argument('--slave', type=int, default=1)
    ap.add_argument('--ch', type=int, default=1, choices=range(1, 5),
                    help='PCB pump channel 1~4 (TIM1)')
    ap.add_argument('--tach', type=int, default=13,
                    help='IR address of Tach Pulse Freq (13~24)')
    ap.add_argument('--steps', default='300,500,700,500,300',
                    help='comma-separated duty values 0~1000')
    ap.add_argument('--dwell', type=float, default=3.0,
                    help='seconds to hold each step (≥ 1.0 for S-Curve settle)')
    args = ap.parse_args()

    hr_duty = HR_PWM_DUTY_BASE + (args.ch - 1)

    cli = ModbusSerialClient(port=args.port, baudrate=args.baud,
                             parity='N', stopbits=1, bytesize=8, timeout=1.0)
    if not cli.connect():
        print(f"[ERR] cannot open {args.port}", file=sys.stderr)
        return 1

    rr = cli.read_input_registers(IR_SYSTEM_TIMER, count=1, device_id=args.slave)
    if rr.isError():
        print(f"[ERR] no response at slave={args.slave}", file=sys.stderr)
        cli.close()
        return 1
    uptime = rr.registers[0]
    print(f"[OK]  uptime={uptime}s  ch=CH{args.ch} (HR{hr_duty})  tach=IR{args.tach}")

    duty0, tach0 = read_status(cli, args.slave, hr_duty, args.tach)
    print(f"Initial: duty={duty0}, tach={tach0} Hz\n")

    steps = [int(x) for x in args.steps.split(',')]
    print(f"Stepping {steps}, dwell {args.dwell}s each (S-Curve adds ~1s ramp)")
    print(f"{'duty':>6}{'%':>6}{'V_est':>8}{'tach Hz':>10}  {'note'}")

    try:
        for d in steps:
            cli.write_register(hr_duty, d, device_id=args.slave)
            time.sleep(args.dwell)
            duty_rb, tach = read_status(cli, args.slave, hr_duty, args.tach)
            note = '' if duty_rb == d else f'(readback={duty_rb})'
            print(f"{d:>6}{d/10:>6.1f}{duty_to_voltage(d):>8.2f}{tach:>10}  {note}")
    except KeyboardInterrupt:
        print("\n[INT] aborted by user")
    finally:
        cli.write_register(hr_duty, 0, device_id=args.slave)
        time.sleep(1.0)
        duty_f, tach_f = read_status(cli, args.slave, hr_duty, args.tach)
        print(f"\nReturned to 0: duty={duty_f}, tach={tach_f} Hz")
        cli.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
