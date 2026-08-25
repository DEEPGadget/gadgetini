GADGETINI SENSOR EXPORTER
Sensor data collection, control board communication, and Prometheus metrics export

═══════════════════════════════════════════════════════════════════════════════

OVERVIEW

The exporter subsystem handles:
- Sensor data collection from Gadgetini (DLC coolant, air, chassis sensors)
- Hardware metrics from Host (CPU, GPU, memory via USB gadget network)
- Control board communication (PCB Modbus) for PWM control and fan curves
- Prometheus metrics export (:9003) for Grafana
- Redis as central data store (shared with display and web UI)

Components:
  data_crawler.py          - Sensor collection loop (auto-detects PCB or legacy ADS1256)
  sensor_exporter.py       - Prometheus HTTP endpoint
  pcb_driver.py            - PCB Modbus communication (CH1-12 PWM, fan tach, health)
  pcb_control.py           - Fan curve controller (auto mode) and manual PWM handler
  dlc_sensors.py           - Sensor I/O (NTC thermistors, DHT11, MPU6050, ADS1256)
  redis_keys.py            - Redis key constants
  pcb_config.yaml          - Fan curve and pump topology configuration

═══════════════════════════════════════════════════════════════════════════════

QUICK START

1. Install Dependencies (Rocky Linux 8.9 / RHEL 10)

  sudo dnf install -y redis python311 python3.11-pip
  sudo systemctl enable --now redis

  sudo python3.11 -m pip install \
    pyserial-asyncio redis jsons rich

2. Configure Serial Permissions

  sudo usermod -aG dialout $USER
  # Log out and back in

3. Run Exporter Components

  # Terminal 1: Sensor collection
  python3 src/exporter/data_crawler.py

  # Terminal 2: Prometheus endpoint
  python3 src/exporter/sensor_exporter.py

4. Enable as systemd Services (optional)

  sudo systemctl enable --now data_crawler.service
  sudo systemctl enable --now sensor_exporter.service

  Service files: src/configure/daemons/gadgetini/

═══════════════════════════════════════════════════════════════════════════════

KEY FILES

redis_keys.py
  Sensor names and Redis key mappings (shared with sensor_exporter, display, web UI)
  - COOLANT_TEMP_INLET1/2, COOLANT_TEMP_OUTLET1/2
  - pwm_duty_pump(i), pwm_duty_fan(i)
  - fan_rpm(i)
  - COMM_STATUS, COMM_CONSECUTIVE_FAILURES

data_crawler.py
  Main sensor collection loop:
  - Auto-detects PCB Modbus backend (preferred) vs. legacy ADS1256
  - Polls sensors every 1-2 seconds
  - Reads from Redis: manual_pwm_target_*, control_mode
  - Writes to Redis: coolant_*, air_*, pwm_duty_*, fan_rpm_*, comm_*

pcb_driver.py
  PCB Modbus communication:
  - Connects to PCB serial (/dev/ttyUSB0)
  - Reads registers: PWM duty (HR 0-3 pump, 4-11 fan), tach feedback, health
  - Writes PWM targets (0-1000 = 0-100%)
  - Health check: comm_status (ok/timeout/disconnected)

pcb_control.py
  Fan curve control (two modes):
  - AUTO:   FanCurveController applies curve from pcb_config.yaml
  - MANUAL: applies duty from manual_pwm_target_* Redis keys

  Watches pcb_config.yaml for live changes (hot reload)
  PWM never goes below min_duty (prevents 0% = 100% fan bug)

dlc_sensors.py
  Hardware sensors:
  - NTC thermistors (10k ohm, Steinhart-Hart curve): inlet/outlet temps
  - DHT11: air temperature & humidity
  - MPU6050: 3-axis accelerometer (chassis stability)
  - ADS1256: legacy ADC (fallback if PCB not present)
  - Auto-detects sensor presence; graceful degradation on failure

sensor_exporter.py
  Prometheus HTTP endpoint (:9003):
  - Reads from Redis every scrape
  - Exposes as gauges: coolant_temp_inlet, pwm_duty_fan_0, etc.
  - Used by Prometheus (:9090) → Grafana (:3000)

pcb_config.yaml
  Fan curve configuration (hot-reloaded by pcb_control.py):
  - Pump topology: channel mapping + flow multiplier
  - Fan curves per temperature source (CPU, GPU, coolant)
  - Idle → Warning temperature thresholds
  - PWM ranges (min_duty, max_duty) per source

═══════════════════════════════════════════════════════════════════════════════

TESTING: Fake Sensor Scenarios

Use the test suite to verify UI behavior without real hardware.

Quick Start:
  python3 src/exporter/test/run_normal.py      # Normal operation
  python3 src/exporter/test/run_warning.py     # Elevated temperature
  python3 src/exporter/test/run_critical.py    # Critical temperature + leak

Each scenario:
  1. Stops data_crawler.service (pauses real collection)
  2. Writes fake sensor data to Redis (30 seconds)
  3. Restarts data_crawler.service

Test files:
  scenario.py           - Defines 3 scenarios (values + variations)
  fake_simulator.py     - Redis writer (generates fake data with variations)
  _common.py            - Service control (stop/start data_crawler)
  run_normal.py         - Entry point for normal scenario
  run_warning.py        - Entry point for warning scenario
  run_critical.py       - Entry point for critical scenario
  README.md             - Detailed test guide + maintenance (adding new variables)

See test/README.md for full documentation.

═══════════════════════════════════════════════════════════════════════════════

TROUBLESHOOTING

"No such file or directory: /dev/ttyUSB0"
  - Check: ls /dev/ttyUSB*
  - Install ftdi driver: sudo modprobe ftdi_sio
  - Verify permissions: ls -l /dev/ttyUSB0
  - Serial device should be readable by 'dialout' group

"Redis connection refused"
  - Check: redis-cli ping (should return PONG)
  - Start Redis: sudo systemctl start redis
  - Check logs: sudo journalctl -u redis -n 20

"ADS1256 not detected, falling back to legacy mode"
  - If you have an ADS1256 attached:
    - Check SPI pins (CE0, MOSI, MISO, SCLK, DRDY)
    - Verify device tree overlay enables SPI: raspi-config
    - Test with: python3 -c "from src.exporter.dlc_sensors import ADS1256; print(ADS1256._init__())"
  - If using PCB Modbus, this is expected

"control_mode not in Redis, defaulting to auto"
  - On first run, web UI hasn't set control_mode yet
  - Normal behavior; mode defaults to 'auto'
  - After web UI sets it, it persists in Redis

═══════════════════════════════════════════════════════════════════════════════

RUNNING AS SYSTEMD SERVICES

Service files (auto-start on boot):
  - src/configure/daemons/gadgetini/data_crawler.service
  - src/configure/daemons/gadgetini/sensor_exporter.service

Enable & start:
  sudo systemctl enable data_crawler.service sensor_exporter.service
  sudo systemctl start data_crawler.service sensor_exporter.service

View logs:
  sudo journalctl -u data_crawler.service -f          # Follow live
  sudo journalctl -u sensor_exporter.service -n 50    # Last 50 lines

Stop for testing:
  sudo systemctl stop data_crawler.service
  # Run manual test or debug
  sudo systemctl start data_crawler.service

═══════════════════════════════════════════════════════════════════════════════

HOST METRICS (data_crawler_host.py)

Runs on host machine; collects CPU/GPU/memory metrics via USB gadget network.
Writes to Gadgetini Redis:
  - cpu_temp_0, cpu_util_0
  - gpu_temp_0..3, gpu_curr_pwr_*
  - mem_usage, mem_total

See src/configure/daemons/host/ for service setup on host.

═══════════════════════════════════════════════════════════════════════════════

REDIS KEYS REFERENCE

See redis_keys.py for complete list. Common ones:

Sensors:
  coolant_temp_inlet1, coolant_temp_outlet1    (°C)
  coolant_flow_lpm                             (L/min)
  coolant_leak, coolant_level                  (0/1, %)
  air_temp, air_humit                          (°C, %)
  chassis_stabil                               (0-7)

Control:
  pwm_duty_pump_0..3                           (0-1000)
  pwm_duty_fan_0..7                            (0-1000)
  fan_rpm_0..7                                 (RPM)
  manual_pwm_target_pump_0..3                  (0-1000, manual mode)
  manual_pwm_target_fan_0..7                   (0-1000, manual mode)
  control_mode                                 ('auto' or 'manual')
  pwm_curve_duty_cpu, pwm_curve_duty_gpu, ...  (per-source duty)
  pwm_curve_selected_source                    (winning source key)

Status:
  comm_status                                  ('ok', 'timeout', 'disconnected')
  comm_consecutive_failures                    (retry count)

═══════════════════════════════════════════════════════════════════════════════
