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
- Gadgetini: `data_crawler.py` collects DLC sensor metrics (coolant, leak, gyro) → Redis
- Redis → Exporter (:9003) → Prometheus (:9090) → Grafana (:3000)
- Redis → TFT Display (reads sensor data)
- Next.js Web (:3001) is a configuration UI for the TFT display (config.ini), not a Redis consumer

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
