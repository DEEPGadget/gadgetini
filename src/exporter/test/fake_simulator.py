"""Simulate control board sensor data by writing to Redis."""

import redis
import time
import random
from typing import Dict, Any

# Import Redis keys from the project
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from redis_keys import (
    COOLANT_TEMP_INLET1, COOLANT_TEMP_INLET2,
    COOLANT_TEMP_OUTLET1, COOLANT_TEMP_OUTLET2,
    COOLANT_FLOW_LPM, COOLANT_LEAK, COOLANT_LEVEL,
    AIR_TEMP, AIR_HUMIT, CHASSIS_STABIL,
    fan_rpm, pwm_duty_pump, pwm_duty_fan,
    pwm_curve_source_duty, PWM_CURVE_SELECTED_SOURCE,
    COMM_STATUS
)

STEP_FRACTION = 0.12  # per-tick step as a fraction of the variation range


class FakeSimulator:
    """Generate and write fake sensor data to Redis."""

    def __init__(self, redis_host='localhost', redis_port=6379):
        self.redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.step = 0
        self._walk_state = {}

    def apply_scenario(self, scenario: Dict[str, Any], interval: float = 2.0):
        """
        Write fake data to Redis based on scenario definition, running until interrupted.

        Args:
            scenario: Scenario dict with base values and variations
            interval: Update interval in seconds
        """
        scenario_name = scenario.get("name", "Unknown")
        variation = scenario.get("variation", {})

        print(f"\n{'='*60}")
        print(f"Starting scenario: {scenario_name}")
        print(f"Update interval: {interval}s (Ctrl+C to stop)")
        print(f"{'='*60}\n")

        self.step = 0
        try:
            while True:
                self._write_frame(scenario, variation)
                self.step += 1
                if self.step % 10 == 0:
                    print(f"  Step {self.step}: scenario running...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print(f"\n⏹  Scenario '{scenario_name}' stopped by user after {self.step} updates\n")

    def _walk(self, key: str, base: float, rng: float, floor=None, ceiling=None) -> float:
        """Bounded random walk — smooth value drift instead of full-range jumps per tick."""
        cur = self._walk_state.get(key, base)
        step = rng * STEP_FRACTION
        cur += random.uniform(-step, step)
        cur = max(base - rng, min(base + rng, cur))  # hard clamp to scenario bound
        if floor is not None:
            cur = max(floor, cur)
        if ceiling is not None:
            cur = min(ceiling, cur)
        self._walk_state[key] = cur
        return cur

    def _write_frame(self, scenario: Dict[str, Any], variation: Dict[str, float]):
        """Write one frame of fake data to Redis."""

        # Coolant temperatures with smoothing
        coolant_temp_range = variation.get("coolant_temp_range", 0.5)
        inlet1 = self._walk("coolant_inlet1", scenario["coolant_inlet1"], coolant_temp_range)
        outlet1 = self._walk("coolant_outlet1", scenario["coolant_outlet1"], coolant_temp_range)
        inlet2 = self._walk("coolant_inlet2", scenario["coolant_inlet2"], coolant_temp_range)
        outlet2 = self._walk("coolant_outlet2", scenario["coolant_outlet2"], coolant_temp_range)

        self.redis.set(COOLANT_TEMP_INLET1, f"{inlet1:.1f}")
        self.redis.set(COOLANT_TEMP_OUTLET1, f"{outlet1:.1f}")
        self.redis.set(COOLANT_TEMP_INLET2, f"{inlet2:.1f}")
        self.redis.set(COOLANT_TEMP_OUTLET2, f"{outlet2:.1f}")

        # Delta T
        delta_t1 = outlet1 - inlet1
        delta_t2 = outlet2 - inlet2
        self.redis.set("coolant_delta_t1", f"{delta_t1:.1f}")
        self.redis.set("coolant_delta_t2", f"{delta_t2:.1f}")

        # Coolant flow
        flow_range = variation.get("flow_range", 0.3)
        flow = self._walk("coolant_flow_lpm", scenario["coolant_flow_lpm"], flow_range, 0)
        self.redis.set(COOLANT_FLOW_LPM, f"{flow:.2f}")

        # Leak and level
        self.redis.set(COOLANT_LEAK, str(scenario["coolant_leak"]))
        self.redis.set(COOLANT_LEVEL, str(scenario["coolant_level"]))

        # Air sensors
        air_temp_range = variation.get("air_temp_range", 0.3)
        air_temp = self._walk("air_temp", scenario["air_temp"], air_temp_range)
        self.redis.set(AIR_TEMP, f"{air_temp:.1f}")
        self.redis.set(AIR_HUMIT, str(scenario["air_humidity"]))

        # Chassis stability
        self.redis.set(CHASSIS_STABIL, str(scenario["chassis_stability"]))

        # Communication status
        self.redis.set(COMM_STATUS, scenario.get("comm_status", "ok"))

        # Fan curve sources: independent walk per source, take the max (mirrors FanCurveController.update)
        curve_duty_range = variation.get("curve_duty_range", 3)
        walked_duties = {}
        for source in scenario.get("pwm_curve_sources", []):
            walked_duty = self._walk(
                f"curve_{source['key']}",
                source["duty"],
                curve_duty_range,
                0,
                100
            )
            walked_duties[source["key"]] = walked_duty
            # Write per-source duty (scale: 0-100 → 0-1000 in 0.1% units)
            self.redis.set(
                pwm_curve_source_duty(source["key"]),
                str(int(round(walked_duty * 10)))
            )

        # Determine winning source (max duty)
        selected_key, fan_duty_pct = max(walked_duties.items(), key=lambda kv: kv[1])
        self.redis.set(PWM_CURVE_SELECTED_SOURCE, selected_key)

        # Fan channels: all get the SAME duty (uniform, from curve's selected source)
        fan_duty_1000 = max(0, min(1000, int(round(fan_duty_pct * 10))))
        for i in range(8):  # CH5-12, 8 channels
            self.redis.set(pwm_duty_fan(i), str(fan_duty_1000))

        # Pump channels: constant, uniform, no jitter (static in real system)
        pump_duty_1000 = max(0, min(1000, int(scenario["pump_duty"] * 10)))
        for i in range(4):  # CH1-4, 4 channels
            self.redis.set(pwm_duty_pump(i), str(pump_duty_1000))

        # Fan RPM: independent walk per channel (tach readback, not computed)
        rpm_range = variation.get("rpm_range", 100)
        for i, base_rpm in enumerate(scenario.get("fan_rpm", [0]*8)):
            rpm = self._walk(f"fan_rpm_{i}", base_rpm, rpm_range, 0)
            self.redis.set(fan_rpm(i), str(int(max(0, rpm))))


def run_scenario(scenario: Dict[str, Any], interval: float = 2.0):
    """Convenience function to run a single scenario."""
    simulator = FakeSimulator()
    simulator.apply_scenario(scenario, interval=interval)
