#!/usr/bin/env python3
"""Quick MCS_IO probe: read system timer + NTC CH13~16 over Modbus RTU.

Usage:
    python3 probe_ntc.py                # auto-detect baud (115200 → 9600)
    python3 probe_ntc.py --baud 9600
    python3 probe_ntc.py --port /dev/serial0 --slave 1
"""
import argparse
import sys
from pymodbus.client import ModbusSerialClient

IR_SYSTEM_TIMER = 0
IR_NTC_BASE = 28
DISCONNECT = -999


def s16(u): return u - 0x10000 if u >= 0x8000 else u


def try_open(port, baud, slave, timeout=1.0):
    cli = ModbusSerialClient(port=port, baudrate=baud, parity='N',
                             stopbits=1, bytesize=8, timeout=timeout)
    if not cli.connect():
        return None
    rr = cli.read_input_registers(IR_SYSTEM_TIMER, count=1, device_id=slave)
    if rr.isError():
        cli.close()
        return None
    return cli, rr.registers[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default='/dev/ttyUSB0')
    ap.add_argument('--slave', type=int, default=1)
    ap.add_argument('--baud', type=int, default=None,
                    help='if omitted, try 115200 then 9600')
    args = ap.parse_args()

    bauds = [args.baud] if args.baud else [115200, 9600]
    for baud in bauds:
        result = try_open(args.port, baud, args.slave)
        if result is not None:
            cli, uptime = result
            print(f"[OK]  port={args.port} baud={baud} slave={args.slave} uptime={uptime}s")
            break
    else:
        print(f"[ERR] No response on {args.port} at {bauds} (slave={args.slave})", file=sys.stderr)
        return 1

    rr = cli.read_input_registers(IR_NTC_BASE, count=4, device_id=args.slave)
    if rr.isError():
        print(f"[ERR] NTC read failed: {rr}", file=sys.stderr)
        cli.close()
        return 1

    print()
    print("NTC channels (IR 28~31, CH13~16):")
    print(f"{'CH':<6}{'IR':<5}{'raw':<8}{'signed':<10}{'°C':<10}{'status'}")
    for i, raw in enumerate(rr.registers):
        signed = s16(raw)
        if signed == DISCONNECT:
            celsius = '-'
            status = 'no sensor'
        else:
            celsius = f"{signed / 10.0:.1f}"
            status = 'connected'
        print(f"CH{13+i:<4}{IR_NTC_BASE+i:<5}{raw:<8}{signed:<10}{celsius:<10}{status}")

    cli.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
