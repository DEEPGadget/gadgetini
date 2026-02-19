# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gadgetini is a server monitoring system for Direct Liquid Cooling (DLC) systems by DeepGadget. It monitors hardware health (CPUs, GPUs, temperatures, coolant levels) on a Raspberry Pi 4 B+ and provides visualization through a physical TFT display and web dashboard.

## Architecture

```
HOST MACHINE                         GADGETINI (Raspberry Pi)
┌─────────────────┐                 ┌──────────────────┐
│ CPU/GPU Metrics │                 │ DLC Sensors      │
│ (psutil)        │◄───Serial───────│ (DHT11, NTC,     │
└────────┬────────┘     UART        │  MPU6050, ADS1256)│
         │                          └────────┬─────────┘
         │                                   │
         └───────────────┬───────────────────┘
                         ▼
                   ┌──────────┐
                   │  Redis   │  (central data hub)
                   └────┬─────┘
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
   ┌──────────┐  ┌───────────┐  ┌────────────┐
   │Prometheus│  │ Next.js   │  │ TFT Display│
   │ :9003    │  │ Web :3000 │  │ (ST7789)   │
   └──────────┘  └───────────┘  └────────────┘
```

**Key data flow:**
- `data_crawler.py` / `data_crawler_host.py` → collect sensor/system metrics → Redis
- `serial_sender_v2.py` ↔ `serial_receiver_v2.py` → bidirectional host-gadgetini communication via async serial (SYN/SYN-ACK/DATA handshake)
- All consumers (display, web, prometheus) read from Redis

## Directory Structure

- `src/display/` - Physical TFT display rendering (ST7789 driver, plotting)
- `src/exporter/` - Sensor collection, Prometheus exporter, serial communication
- `src/exporter/daemon/` - systemd service files for gadgetini and host
- `src/gui/gadgetini-web/` - Next.js 15 web dashboard
- `src/configure/` - USB gadget network setup scripts

## Common Commands

### Web Dashboard (src/gui/gadgetini-web/)
```bash
npm run dev       # Development server on :3000
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
python3 src/exporter/data_crawler.py        # Sensor data collection
python3 src/exporter/sensor_exporter.py     # Prometheus endpoint :9003
python3 src/exporter/serial_sender_v2.py    # Host-side serial sender
python3 src/exporter/serial_receiver_v2.py  # Gadgetini-side serial receiver
python3 src/display/display_main.py         # TFT display driver
```

### systemd Services
Service files in `src/exporter/daemon/gadgetini/` and `src/exporter/daemon/host/`
```bash
sudo systemctl enable --now redis
sudo systemctl enable sensor_exporter.service
sudo systemctl enable serial_receiver.service
sudo systemctl enable data_crawler.service
```

### USB Network Configuration
```bash
sudo bash src/configure/usb-gadget-host.sh
sudo bash src/configure/usb-gadget-gadgetini.sh
```

## Key Files

- `src/exporter/dlc_sensors.py` - Sensor abstractions (temperature via Steinhart-Hart, leak detection, gyro)
- `src/exporter/serial_sender_v2.py` / `serial_receiver_v2.py` - Async serial protocol with handshaking
- `src/display/display_main.py` - Main display loop reading from Redis
- `src/display/config.ini` - Display layout configuration
- `src/gui/gadgetini-web/app/api/` - Next.js API routes for node health, system control

## Redis Keys

Data is cached in Redis with keys like: `coolant_temp`, `coolant_leak`, `cpu_temp_0`, `gpu_temp_*`, `mem_*`, `cpu_*`

## Hardware Context

- **Display**: Adafruit 1.9" 320x170 ST7789 TFT
- **ADC**: ADS1256 via Waveshare High-Precision AD/DA Board
- **Sensors**: DHT11 (humidity/temp), 10k NTC thermistor (coolant), MPU6050 (chassis stability), liquid leak/level/flow sensors

## Hardcoded Paths

Code assumes these installation paths:
- Gadgetini: `/home/gadgetini/gadgetini/`
- ADS1256 driver: `/home/gadgetini/High-Precision-AD-DA-Board-Code/RaspberryPI/ADS1256/python3`
