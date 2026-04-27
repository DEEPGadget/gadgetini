#!/usr/bin/env python3
"""Boot-time PCB detector.

Probes Modbus RTU on the production port (/dev/serial0) and a USB-RS485
fallback (/dev/ttyUSB0). On detection, attempts to start
control_board.service. On no-detection, exits cleanly so the existing
data_crawler.service handles collection via its own autostart.

Logs go to stdout/stderr → journald (journalctl -u pcb_bootstrap.service).
Always exits 0 so the boot sequence is never blocked by detection failure.
"""
import subprocess
import sys

PORTS = ['/dev/serial0', '/dev/ttyUSB0']
BAUDS = [115200, 9600]
SLAVE = 1
PROBE_TIMEOUT = 1.5

try:
    from pymodbus.client import ModbusSerialClient
except ImportError:
    print("pymodbus not installed — cannot probe PCB, deferring to data_crawler",
          file=sys.stderr)
    sys.exit(0)


def probe(port, baud):
    cli = ModbusSerialClient(port=port, baudrate=baud, parity='N',
                             stopbits=1, bytesize=8, timeout=PROBE_TIMEOUT)
    try:
        if not cli.connect():
            return False
        rr = cli.read_input_registers(0, count=1, device_id=SLAVE)
        return rr is not None and not rr.isError()
    except Exception:
        return False
    finally:
        try: cli.close()
        except Exception: pass


def detect():
    for port in PORTS:
        for baud in BAUDS:
            if probe(port, baud):
                return port, baud
    return None, None


def systemctl_start(unit):
    r = subprocess.run(['systemctl', 'start', unit],
                       capture_output=True, text=True, timeout=15)
    return r.returncode == 0, (r.stderr or r.stdout).strip()


def main():
    print("probing serial ports for PCB...")
    port, baud = detect()

    if port is None:
        print("no PCB detected — data_crawler.service will run via its own autostart")
        return 0

    print(f"PCB detected on {port} @ {baud} bps, slave {SLAVE}")
    print("starting control_board.service...")
    ok, err = systemctl_start('control_board.service')
    if ok:
        print("control_board.service started")
    else:
        print(f"control_board.service start failed: {err}", file=sys.stderr)
        print("data_crawler.service remains as fallback", file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
