#!/usr/bin/env python3
"""
Run control board test scenarios.

Steps:
1. Stop real data collection (data_crawler.service)
2. Run fake simulator (writes to Redis)
3. Restart real data collection
"""

import subprocess
import sys
import time
import argparse

from scenario import ALL_SCENARIOS, SCENARIO_NORMAL, SCENARIO_WARNING, SCENARIO_CRITICAL
from fake_simulator import run_scenario


SERVICE_NAME = "data_crawler.service"


def stop_service():
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


def start_service():
    """Start the data collection service."""
    print(f"\n[3/3] Restarting {SERVICE_NAME}...")
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


def run_test(scenario_name: str, interval: float = 0.5):
    """Run a test scenario."""
    scenario_map = {
        "normal": SCENARIO_NORMAL,
        "warning": SCENARIO_WARNING,
        "critical": SCENARIO_CRITICAL,
    }

    if scenario_name.lower() not in scenario_map:
        print(f"✗ Unknown scenario: {scenario_name}")
        print(f"  Available: {', '.join(scenario_map.keys())}")
        return False

    scenario = scenario_map[scenario_name.lower()]

    # Stop real service
    if not stop_service():
        return False

    time.sleep(1)

    # Run fake simulator
    print(f"\n[2/3] Running fake simulator...")
    try:
        run_scenario(scenario, interval=interval)
    except Exception as e:
        print(f"  ✗ Error running simulator: {e}")
        # Still try to restart service
        start_service()
        return False

    time.sleep(1)

    # Restart real service
    if not start_service():
        return False

    print(f"\n{'='*60}")
    print(f"Test completed successfully!")
    print(f"{'='*60}\n")
    return True


def list_scenarios():
    """Print available scenarios."""
    print("\nAvailable test scenarios:")
    print("─" * 60)
    for i, scenario in enumerate(ALL_SCENARIOS, 1):
        name = scenario.get("name", "Unknown")
        duration = scenario.get("duration_seconds", 0)
        print(f"  {i}. {name:<40} ({duration}s)")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Run control board test scenarios with fake data"
    )
    parser.add_argument(
        "scenario",
        nargs="?",
        help="Scenario to run: normal, warning, critical (default: normal)"
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List all available scenarios"
    )
    parser.add_argument(
        "-i", "--interval",
        type=float,
        default=0.5,
        help="Update interval in seconds (default: 0.5)"
    )

    args = parser.parse_args()

    if args.list:
        list_scenarios()
        return 0

    scenario_name = args.scenario or "normal"

    print(f"\n{'='*60}")
    print(f"GADGETINI CONTROL BOARD TEST SCENARIO RUNNER")
    print(f"{'='*60}")

    if not run_test(scenario_name, interval=args.interval):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
