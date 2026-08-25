# Control Board Test Scenarios

Fake data simulator for testing the control board UI without real hardware or ongoing sensor measurements.

## Overview

Three predefined scenarios to test different operational states:

1. **Normal** - Stable operation (35-40°C, 1500-2000 RPM, 40-60% PWM)
2. **Warning** - Elevated temperature (45-50°C, 2500-3500 RPM, 70-85% PWM)
3. **Critical** - Very high temperature + leak (55-60°C, 4000-5000 RPM, 90-100% PWM, leak detected)

## Files

- `_common.py` - Common utilities (service control, test orchestration)
- `scenario.py` - Scenario definitions (normal, warning, critical)
- `fake_simulator.py` - Redis writer that generates fake sensor data
- `run_normal.py` - Run normal scenario test
- `run_warning.py` - Run warning scenario test
- `run_critical.py` - Run critical scenario test
- `README.md` - This file

## How It Works

When you run a test:

1. **Stop** `data_crawler.service` (pauses real sensor collection)
2. **Run** fake simulator (writes hardcoded values + small variations to Redis)
3. **Restart** `data_crawler.service` (resumes real sensor collection)

This prevents conflicts between real measurements and test data.

## Usage

### Run Normal scenario (default interval 0.5s)
```bash
python3 src/control/test/run_normal.py
```

### Run Warning scenario
```bash
python3 src/control/test/run_warning.py
```

### Run Critical scenario
```bash
python3 src/control/test/run_critical.py
```

Each scenario runs for 30 seconds by default, with updates every 0.5 seconds (twice per second).

### Quick reference
```bash
# All three scenarios sequentially (for complete testing)
python3 src/control/test/run_normal.py && \
python3 src/control/test/run_warning.py && \
python3 src/control/test/run_critical.py
```

## What Gets Written to Redis

Each scenario writes:

- **Coolant temperatures** (inlet1, outlet1, inlet2, outlet2) with ±0.5-1.5°C variation
- **Coolant flow** (L/min) with small variations
- **Leak sensor** (0 = normal, 1 = leak detected)
- **Coolant level** (percentage)
- **Air temperature & humidity**
- **Chassis stability** indicator
- **PWM duty** for pumps (CH1-4) and fans (CH5-12) - 0-1000 (0-100%)
- **Fan RPM** for all 8 fan channels

## Notes

- Variations are realistic (values don't jump around randomly)
- Each scenario runs for 30 seconds by default
- You'll see progress output every 10 updates
- Requires Redis to be running (`sudo systemctl status redis`)
- Requires `redis-py` package

## Example Output

```
============================================================
GADGETINI CONTROL BOARD TEST SCENARIO RUNNER
============================================================

[1/3] Stopping data_crawler.service...
  ✓ data_crawler.service stopped

[2/3] Running fake simulator...

============================================================
Starting scenario: Normal Operation
Duration: 30s, Update interval: 0.5s
============================================================

  Step 0: Inlet1=37.2°C, Flow=3.4L/min, Leak=0, RPM[0]=1850
  Step 10: Inlet1=37.8°C, Flow=3.6L/min, Leak=0, RPM[0]=1820
  Step 20: Inlet1=36.9°C, Flow=3.3L/min, Leak=0, RPM[0]=1880

✓ Scenario 'Normal Operation' completed (60 updates)

[3/3] Restarting data_crawler.service...
  ✓ data_crawler.service restarted

============================================================
Test completed successfully!
============================================================
```

## Viewing Test Data

While the test runs, you can view the Redis data:

```bash
redis-cli
> GET coolant_temp_inlet1
> GET pwm_duty_fan_0
> GET coolant_leak
```

Or monitor in real-time:

```bash
redis-cli MONITOR
```

## Maintenance: Adding/Removing Redis Variables

When a new sensor or control parameter is added to the system, update the test scenarios like this:

### Step 1: Add variable to scenario definitions

Edit `scenario.py` and add the new variable to `SCENARIO_NORMAL`, `SCENARIO_WARNING`, and `SCENARIO_CRITICAL`:

```python
SCENARIO_NORMAL = {
    "name": "Normal Operation",
    ...
    "coolant_inlet1": 37.0,
    "coolant_outlet1": 39.0,
    "new_sensor_value": 25.5,      # ← Add here
    "variation": {
        "coolant_temp_range": 0.5,
        "new_sensor_range": 1.0,   # ← Add variation range here
    }
}
```

### Step 2: Add Redis writer in fake_simulator.py

Edit `fake_simulator.py` and add the variable in `_write_frame()`:

```python
def _write_frame(self, scenario: Dict[str, Any], variation: Dict[str, float]):
    ...
    # New sensor with variation
    sensor_var = variation.get("new_sensor_range", 0.5)
    new_value = scenario["new_sensor_value"] + random.uniform(-sensor_var, sensor_var)
    self.redis.set("new_sensor_key", f"{new_value:.1f}")
    ...
```

### What NOT to change

These files **do NOT need modification** when adding variables:
- ✅ `_common.py` - Handles service control automatically
- ✅ `run_normal.py` - Just passes scenario to common handler
- ✅ `run_warning.py` - Just passes scenario to common handler
- ✅ `run_critical.py` - Just passes scenario to common handler

### Removing a variable

Simply reverse the process:
1. Remove it from `scenario.py` (all 3 scenarios)
2. Remove the Redis writer from `fake_simulator.py`

The run scripts don't need changes.

### Complete example: Adding "pump_power_watts"

**In `scenario.py`:**
```python
SCENARIO_NORMAL = {
    ...
    "pump_power_watts": 15.0,  # Add base value
    "variation": {
        ...,
        "pump_power_range": 2.0,  # ±2W variation
    }
}
```

**In `fake_simulator.py`:**
```python
def _write_frame(self, scenario, variation):
    ...
    power_var = variation.get("pump_power_range", 1.0)
    pump_power = scenario["pump_power_watts"] + random.uniform(-power_var, power_var)
    self.redis.set("pump_power_watts", f"{max(0, pump_power):.1f}")
    ...
```

Done! All three run scripts automatically use the updated scenarios.

## Troubleshooting

**"Error: Permission denied" when stopping service**
- Run with `sudo python3 src/control/test/run_test.py ...`
- Or configure sudoers to allow systemctl without password

**"Redis connection failed"**
- Ensure Redis is running: `sudo systemctl status redis`
- Check Redis port is 6379: `redis-cli ping` (should return PONG)

**Service won't restart**
- Check service status: `sudo systemctl status data_crawler.service`
- View logs: `sudo journalctl -u data_crawler.service -n 20`
