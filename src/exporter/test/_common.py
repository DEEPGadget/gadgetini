"""Common utilities for test scenarios."""

import subprocess
import time
import signal


SERVICE_NAME = "data_crawler.service"


def _raise_keyboard_interrupt(signum, frame):
    """Convert SIGTERM to KeyboardInterrupt for graceful shutdown."""
    raise KeyboardInterrupt()


def stop_service() -> bool:
    """Stop the data collection service."""
    print(f"\n[1/3] Stopping {SERVICE_NAME}...")
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "stop", SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            print(f"  ⚠ Service stop returned: {result.returncode}")
            if result.stderr:
                print(f"  stderr: {result.stderr}")
        else:
            print(f"  ✓ {SERVICE_NAME} stopped")
    except Exception as e:
        print(f"  ✗ Error stopping service: {e}")
        return False
    return True


def start_service() -> bool:
    """Start the data collection service."""
    print(f"[3/3] Restarting {SERVICE_NAME}...")
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "start", SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            print(f"  ⚠ Service start returned: {result.returncode}")
            if result.stderr:
                print(f"  stderr: {result.stderr}")
        else:
            print(f"  ✓ {SERVICE_NAME} restarted")
    except Exception as e:
        print(f"  ✗ Error starting service: {e}")
        return False
    return True


def run_test_scenario(scenario: dict, interval: float = 2.0) -> bool:
    """
    Run a test scenario with automatic service control.

    Guarantees service restart on any exit path (Ctrl+C, SIGTERM, error, etc).

    Args:
        scenario: Scenario dict from scenario.py
        interval: Update interval in seconds

    Returns:
        True if successful or user-interrupted, False if error occurred
    """
    # Register SIGTERM → KeyboardInterrupt translator
    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)

    # Stop real service
    if not stop_service():
        return False

    time.sleep(1)

    # Run fake simulator
    print(f"\n[2/3] Running fake simulator... (Ctrl+C to stop)\n")
    interrupted = False
    ok = True
    try:
        from fake_simulator import run_scenario
        run_scenario(scenario, interval=interval)
    except KeyboardInterrupt:
        interrupted = True
    except Exception as e:
        print(f"  ✗ Error running simulator: {e}")
        ok = False
    finally:
        # Hard guarantee: always restart the service, regardless of how we exited
        time.sleep(1)
        if not start_service():
            print("  ✗✗ WARNING: failed to restart data_crawler.service — "
                  "run manually: sudo systemctl start data_crawler.service")
            ok = False

    if ok:
        status_msg = "Stopped by user" if interrupted else "Test completed"
        print(f"\n{'='*60}")
        print(f"✓ {status_msg} — service restored")
        print(f"{'='*60}\n")

    return ok
