#!/usr/bin/env python3
"""Runtime PCB watcher.

After boot, periodically probes for the PCB control board on the same
ports/bauds as pcb_bootstrap. If the PCB is detected while
control_board.service is not yet active, starts it — control_board's
`Conflicts=data_crawler.service` directive then auto-stops the legacy
collector.

Skips probing whenever control_board.service is already active to avoid
contending for the serial bus that the running gateway owns.

Logs go to journald (journalctl -u pcb_watcher.service).
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pcb_bootstrap import detect

POLL_INTERVAL = 1     # seconds between probes when control_board is inactive
PROBE_TIMEOUT = 0.4   # per port×baud attempt; OFF worst case ≈ 4 × 0.4s = 1.6s
                      # — keeps watcher responsive during mainboard power cycling
                      # at boot (control board power follows mainboard).


def is_active(unit):
    r = subprocess.run(['systemctl', 'is-active', '--quiet', unit])
    return r.returncode == 0


def systemctl_start(unit):
    r = subprocess.run(['systemctl', 'start', unit],
                       capture_output=True, text=True, timeout=15)
    return r.returncode == 0, (r.stderr or r.stdout).strip()


def main():
    print(f"pcb_watcher started (interval={POLL_INTERVAL}s)")
    while True:
        try:
            if is_active('control_board.service'):
                # Gateway already owns the serial bus — never probe.
                pass
            else:
                port, baud = detect(timeout=PROBE_TIMEOUT)
                if port is not None:
                    print(f"PCB detected on {port} @ {baud} bps — starting control_board.service")
                    ok, err = systemctl_start('control_board.service')
                    if ok:
                        print("control_board.service started "
                              "(data_crawler.service auto-stopped via Conflicts=)")
                    else:
                        print(f"control_board.service start failed: {err}",
                              file=sys.stderr)
        except Exception as e:
            print(f"watcher tick failed: {e}", file=sys.stderr)
        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    sys.exit(main())
