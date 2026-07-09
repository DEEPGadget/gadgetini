# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gadgetini is a server monitoring system for Direct Liquid Cooling (DLC) systems by DeepGadget. It monitors hardware health (CPUs, GPUs, temperatures, coolant levels) on a Raspberry Pi 4 B+ and provides visualization through a physical TFT display and web dashboard.

## Architecture

```
 HOST (dg5W)              GADGETINI (Raspberry Pi 4)
                          ┌─────────────────────────────────────────────┐
┌──────────────┐          │ ┌──────────┐    ┌──────────────┐           │
│data_crawler_ │─USB Net─▶│ │          │◀───│data_crawler  │◀─Sensors  │
│host.py       │ TCP/IPv6 │ │  Redis   │    │.py           │  (NTC,    │
│(CPU/GPU/NIC) │          │ │          │    └──────────────┘   DHT11,  │
└──────────────┘          │ └────┬─────┘                       MPU6050)│
                          │      │                                     │
                          │ ┌────┴─────────────┐                       │
                          │ ▼                   ▼                       │
                          │ ┌────────┐   ┌──────────┐                  │
                          │ │  TFT   │   │ Exporter │                  │
                          │ │Display │   │  :9003   │                  │
                          │ └────────┘   └────┬─────┘                  │
                          │      ▲            ▼                        │
                          │ ┌─────────┐  ┌──────────┐  ┌────────┐     │
                          │ │Next.js  │  │Prometheus│─▶│Grafana │     │
                          │ │Web:3001 │  │  :9090   │  │ :3000  │     │
                          │ └─────────┘  └──────────┘  └────────┘     │
                          │ (config.ini)                               │
                          └─────────────────────────────────────────────┘
```

**Key data flow:**
- Host: `data_crawler_host.py` collects CPU/GPU/NIC metrics → writes directly to Gadgetini Redis via USB gadget network (TCP/IPv6)
- Gadgetini: a single `data_crawler.py` collects DLC sensor metrics (coolant, leak, gyro, air temp/humidity) → Redis. It auto-detects the backend at startup — PCB control board (Modbus RTU) when no ADS1256 is present, else legacy ADS1256 (SPI). Air temp/humidity and gyro are Pi-attached on both paths.
- Redis → Exporter (:9003) → Prometheus (:9090) → Grafana (:3000)
- Redis → TFT Display (reads sensor data)
- Next.js Web (:3001) is a configuration UI for the TFT display (config.ini), not a Redis consumer

## Directory Structure

- `src/display/` - Physical TFT display rendering (ST7789 driver, plotting)
- `src/exporter/` - Sensor collection, Prometheus exporter, serial communication
- `src/configure/daemons/` - systemd service files for gadgetini and host
- `src/gui/gadgetini-web/` - Next.js 15 web dashboard
- `src/configure/` - USB gadget network setup scripts

## Common Commands

### Web Dashboard (src/gui/gadgetini-web/)
```bash
npm run dev       # Development server on :3001
npm run build     # Production build
npm run start     # Run production build
npm run lint      # ESLint
```

### Python Backend
```bash
# Install dependencies (Rocky Linux 8.9 / RHEL 10)
sudo dnf install -y redis python311 python3.11-pip lm_sensors
sudo python3.11 -m pip install pyserial-asyncio redis jsons rich

# Run components manually
python3 src/exporter/data_crawler.py        # Sensor data collection (auto-detects PCB / ADS1256)
python3 src/exporter/sensor_exporter.py     # Prometheus endpoint :9003
python3 src/exporter/data_crawler_host.py   # Host-side metrics → Gadgetini Redis over USB net
python3 src/display/display_main.py         # TFT display driver
```

### systemd Services
Service files in `src/configure/daemons/gadgetini/` and `src/configure/daemons/host/`
```bash
sudo systemctl enable --now redis
sudo systemctl enable --now data_crawler.service
sudo systemctl enable --now sensor_exporter.service
```

### USB Network Configuration
```bash
sudo bash src/configure/usb-gadget-host.sh
sudo bash src/configure/usb-gadget-gadgetini.sh
```

## Key Files

- `src/exporter/dlc_sensors.py` - Pi-attached sensors (ADS1256 coolant via Steinhart-Hart, HDC302x/DHT11 air, MPU6050 gyro) + graceful ADS1256 fallback
- `src/exporter/pcb_driver.py` - PCB Modbus driver (PCBDriver, health_check/poll, detect_backend, apply_initial_state)
- `src/exporter/pcb_control.py` - Fan/pump control via temperature curve (FanCurveController, ConfigReloader) + pcb_config.yaml hot-reload. Ensures PWM is never 0 (which = 100% fan speed)
- `src/exporter/legacy/serial_sender_v2.py` / `serial_receiver_v2.py` - Legacy async serial host link (superseded by USB gadget network)
- `src/display/display_main.py` - Main display loop reading from Redis
- `src/display/config.ini` - Display layout configuration
- `src/gui/gadgetini-web/app/api/` - Next.js API routes for node health, system control

## Redis Keys

**Coolant System:**
- `coolant_temp_inlet1`, `coolant_temp_outlet1`, `coolant_temp_inlet2`, `coolant_temp_outlet2` (°C, from NTC thermistors)
- `coolant_delta_t1`, `coolant_delta_t2` (temperature difference)
- `coolant_level`, `coolant_leak`, `coolant_flow_lpm` (flow estimate)

**Fan/Pump Control:**
- `pwm_duty_pump_0..3` (pump CH1~4, 0~1000 = 0~100%, readback from PCB registers via poll)
- `pwm_duty_fan_0..7` (fan CH5~12, 0~1000, readback from PCB registers via poll)
- `fan_rpm_0..7` (fan tachometer readings, RPM, sticky: only set if tach ever >0)
- `manual_pwm_target_pump_0..3` (pump CH1~4 manual mode targets, 0~1000, clamped to [min_duty, max_duty] on apply)
- `manual_pwm_target_fan_0..7` (fan CH5~12 manual mode targets, 0~1000)
- `control_mode` ('auto' = FanCurveController applies duty from temp curve, 'manual' = applies duty from manual_pwm_target_* keys)

**Host Metrics (from data_crawler_host.py):**
- `cpu_temp_0`, `gpu_temp_0..3`, `gpu_curr_pwr_*`, `mem_usage`, `mem_total`

**System Status:**
- `comm_status` ('ok' / 'timeout' / 'disconnected')
- `comm_consecutive_failures` (PCB communication retry count)

## Hardware Context

- **Display**: Adafruit 1.9" 320x170 ST7789 TFT
- **ADC**: ADS1256 via Waveshare High-Precision AD/DA Board
- **Sensors**: DHT11 (humidity/temp), 10k NTC thermistor (coolant), MPU6050 (chassis stability), liquid leak/level/flow sensors

## Hardcoded Paths

Code assumes these installation paths:
- Gadgetini: `/home/gadgetini/gadgetini/`
- ADS1256 driver: `/home/gadgetini/High-Precision-AD-DA-Board-Code/RaspberryPI/ADS1256/python3`
