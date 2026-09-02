#!/usr/bin/env python3
"""Run Warning scenario test."""

import sys
from _common import run_test_scenario
from scenario import SCENARIO_WARNING

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"GADGETINI CONTROL BOARD TEST - WARNING SCENARIO")
    print(f"{'='*60}")

    success = run_test_scenario(SCENARIO_WARNING, interval=2.0)
    sys.exit(0 if success else 1)
