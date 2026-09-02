"""Simulate control board sensor data by writing to Redis.

Sensors are faked; the PWM control path is NOT. Duty is produced by the production
pcb_control.FanCurveController / ConfigReloader running against the simulated
temperatures, with only the Modbus transport replaced (_SimPCB). So a fan-curve or
pump-duty edit in pcb_config.yaml — e.g. from the web UI — moves simulated PWM
exactly as it would move real hardware, hot-reload included.
"""

import redis
import time
import random
import yaml
from typing import Dict, Any

# Import Redis keys from the project
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pcb_control
import pcb_driver
from redis_keys import (
    COOLANT_TEMP_INLET1, COOLANT_TEMP_INLET2,
    COOLANT_TEMP_OUTLET1, COOLANT_TEMP_OUTLET2,
    COOLANT_FLOW_LPM, COOLANT_LEAK, COOLANT_LEVEL,
    AIR_TEMP, AIR_HUMIT, CHASSIS_STABIL,
    fan_rpm, pwm_duty_pump, pwm_duty_fan,
    CONTROL_MODE, COMM_STATUS
)

STEP_FRACTION = 0.12  # per-tick step as a fraction of the variation range

PCB_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pcb_config.yaml')


class _SimPCB(pcb_driver.PCBDriver):
    """PCBDriver with register writes redirected to Redis instead of Modbus.

    Everything above the transport — pump clamping, apply_initial_state, the fan
    curve — is the real implementation, so the simulator cannot drift from the
    hardware behaviour it stands in for. Writes land on the same pwm_duty_* keys
    PCBDriver.poll() would publish from register readback.
    """

    def __init__(self, cfg, rd):
        super().__init__(cfg)
        self.rd = rd

    def _store_duty(self, ch, value):
        duty = max(0, min(1000, int(value)))
        if 1 <= ch <= 4:
            self.rd.set(pwm_duty_pump(ch - 1), str(duty))
        elif 5 <= ch <= 12:
            self.rd.set(pwm_duty_fan(ch - 5), str(duty))

    def write_register(self, address, value):
        ch = address - pcb_driver.HR_PWM_DUTY_BASE + 1
        if 1 <= ch <= 12:                 # PWM duty; freq/DOUT registers are no-ops
            self._store_duty(ch, value)
        return True

    def write_registers(self, address, values):
        for offset, value in enumerate(values):
            self.write_register(address + offset, value)
        return True


class FakeSimulator:
    """Generate and write fake sensor data to Redis."""

    def __init__(self, redis_host='localhost', redis_port=6379, config_path=PCB_CONFIG_PATH):
        self.redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.step = 0
        self._walk_state = {}

        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        self.pcb = _SimPCB(cfg, self.redis)
        self.reloader = pcb_control.ConfigReloader(config_path, cfg)
        # Boot state: pump duty + DOUT from initial_pwm_duty, same as a real connect.
        self.pcb.apply_initial_state()
        self.redis.set(CONTROL_MODE, 'auto')

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

        # PWM: production control path against the temps just written above, so duty
        # follows pcb_config.yaml. maybe_reload picks up a web-UI curve edit within
        # one frame; pump duty comes from initial_pwm_duty via apply_initial_state.
        controller = self.reloader.maybe_reload(self.pcb)
        if (self.redis.get(CONTROL_MODE) or 'auto') == 'manual':
            pcb_control.apply_manual_pwm(self.pcb, self.redis, self.reloader.cfg)
        else:
            controller.update(self.pcb, self.redis)

        # Fan RPM: independent walk per channel (tach readback, not computed)
        rpm_range = variation.get("rpm_range", 100)
        for i, base_rpm in enumerate(scenario.get("fan_rpm", [0]*8)):
            rpm = self._walk(f"fan_rpm_{i}", base_rpm, rpm_range, 0)
            self.redis.set(fan_rpm(i), str(int(max(0, rpm))))


def run_scenario(scenario: Dict[str, Any], interval: float = 2.0):
    """Convenience function to run a single scenario."""
    simulator = FakeSimulator()
    simulator.apply_scenario(scenario, interval=interval)
