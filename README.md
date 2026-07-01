# gadgetini

gadgetini is a server monitoring system specialized for Direct Liquid Cooling (DLC) systems in [DeepGadget](https://deepgadget.com/) servers (dg5w / dg5r). It collects DLC sensor data on a Raspberry Pi 4 B+, drives a physical TFT status display, runs a fan/pump controller via a custom RS485 control board (PCB), and exposes Prometheus metrics + a Next.js configuration web UI.

![manycore_logo_black (3)](https://github.com/user-attachments/assets/2e65773a-b1cc-46ee-8831-7d3d95a5b798)

## Quick Start

```bash
git clone https://github.com/DEEPGadget/gadgetini.git /home/gadgetini/gadgetini
cd /home/gadgetini/gadgetini

# Enable the collector + supporting services (see Installation for the full list)
sudo cp src/configure/daemons/gadgetini/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now redis data_crawler sensor_exporter
```

A single `data_crawler.service` collects sensor data. It **auto-detects the backend at
startup** — no bootstrap/probe service is involved:

- **ADS1256 present** (legacy Gen1~2 hw) → reads coolant NTC over the ADS1256 (SPI).
- **ADS1256 absent** (Gen3 control-board hw) → talks to the PCB over Modbus RTU and
  tracks PCB liveness with a per-cycle health check.

Either way, air temp/humidity and chassis gyro come from Pi-attached sensors, so the
same image runs on both hardware generations.

Verify:

```bash
sudo journalctl -u data_crawler.service -n 20
redis-cli mget coolant_temp_inlet1 coolant_leak comm_status
curl -s http://localhost:9003/metrics | grep dlc_system_sensor | head
```

## Architecture

```
 HOST (dg5W)              GADGETINI (Raspberry Pi 4)
                          ┌─────────────────────────────────────────────┐
┌──────────────┐          │ ┌──────────┐    ┌──────────────┐           │
│data_crawler_ │─USB Net─▶│ │          │◀───│ data_crawler │           │
│host.py       │ TCP/IPv6 │ │  Redis   │    │  (single)    │           │
│(CPU/GPU/NIC) │          │ │          │    │  auto-detect:│           │
└──────────────┘          │ │          │    │   PCB Modbus ┼─RS485────── PCB control board
                          │ │          │    │   or ADS1256 ┼─SPI──────── ADS1256 (legacy hw)
                          │ │          │    │   + Pi env   ┼─I2C/GPIO─── HDC302x/DHT11, MPU6050
                          │ └────┬─────┘    └──────────────┘           │
                          │      │                                     │
                          │      ▼                                     │
                          │ ┌────────┐   ┌──────────┐                  │
                          │ │  TFT   │   │ Exporter │                  │
                          │ │Display │   │  :9003   │                  │
                          │ └────────┘   └────┬─────┘                  │
                          │                   ▼                        │
                          │ ┌─────────┐  ┌──────────┐  ┌────────┐     │
                          │ │Next.js  │  │Prometheus│─▶│Grafana │     │
                          │ │UI :3001 │  │  :9090   │  │ :3000  │     │
                          │ └─────────┘  └──────────┘  └────────┘     │
                          └─────────────────────────────────────────────┘
```

### Single collector, runtime backend detection

`data_crawler.py` selects its backend once at startup via
[`pcb_driver.detect_backend()`](src/exporter/pcb_driver.py), which keys off ADS1256
presence (a Pi SPI board, deterministic and independent of mainboard power):

- **PCB path** — `pcb_driver.PCBDriver` opens the Modbus serial port and runs a cheap
  per-cycle `health_check()`. When the PCB answers it polls coolant/leak/level/flow and
  applies the fan curve ([`pcb_control.FanCurveController`](src/exporter/pcb_control.py));
  when it does not, the loop skips the PCB poll but keeps collecting Pi-attached sensors.
- **Legacy path** — `dlc_sensors.poll_coolant()` reads coolant NTC from the ADS1256.

There is no `pcb_bootstrap` / `pcb_watcher` / `control_board` service and no systemd
`Conflicts=` — backend selection and PCB liveness live entirely inside `data_crawler.py`.

> **Power note (Rev_C vs Rev_D).** On the current board (**Rev_C**) the PCB is powered
> only by the mainboard 12V rail, so it is off whenever the server is off — coolant/leak/
> level sensing requires the mainboard to be on, while air temp/humidity and gyro stay
> available because they are Pi-attached. The next board (**Rev_D**) adds 5V standby so the
> PCB can sense continuously; those env sensors then migrate onto the PCB.

## Hardware

- **Compute**: Raspberry Pi 4 B+ (Raspbian 12 bookworm)
- **PCB control board** (Gen3 hw): isolated RS485 Modbus RTU, 12 PWM channels (TIM1 1 kHz pump × 4, TIM2 25 kHz fan × 4, TIM8 25 kHz fan × 4), pulse tach inputs, ADC, DIN/AIN
- **Display**: Adafruit 1.9" 320×170 ST7789 TFT
- **Cooling sensors** (via PCB): 10k NTC × up to 4 (inlet1/outlet1/inlet2/outlet2), liquid leak (AIN), liquid level (DIN), waterflow (estimated from pump duty)
- **Environment sensors** (Pi-attached, both hw generations): DHT11 or HDC302x (auto-detect, RPi I²C/GPIO), MPU6050 gyro for chassis stability (dg5w only)
- **Legacy ADC** (Gen1~2 hw only): Waveshare High-Precision AD/DA (ADS1256, SPI)

## Services

All systemd units in [src/configure/daemons/gadgetini/](src/configure/daemons/gadgetini/):

| Service | Type | Purpose |
|---|---|---|
| `redis.service` | always-on | Sensor cache |
| `data_crawler.service` | always-on | Unified collector — auto-detects PCB Modbus or legacy ADS1256, drives fan curve, writes to Redis |
| `sensor_exporter.service` | always-on | Prometheus endpoint on `:9003` |
| `gadgetini_ui.service` | always-on | Next.js config UI on `:3001` |
| `display_pannel.service` | always-on | TFT live status loop |
| `display_logo.service` | oneshot | Boot splash on TFT |
| `usb-gadget-up.service` | oneshot | NetworkManager up for the USB gadget link to the host |

PCB port/baud is auto-resolved by `data_crawler` from [pcb_config.yaml](src/exporter/pcb_config.yaml) (tries `/dev/serial0`, `/dev/ttyUSB0` at 115200/9600), so a board on a non-default baud still connects without config edits.

## Redis Keys

Flat naming, consumed by `sensor_exporter`:

| Key | Unit | Source |
|---|---|---|
| `coolant_temp_inlet1` / `inlet2` | °C | NTC via PCB (IR 28 / IR 31) or ADS1256 |
| `coolant_temp_outlet1` / `outlet2` | °C | NTC via PCB (IR 29 / IR 30) or ADS1256 |
| `coolant_delta_t1` / `delta_t2` | °C | Computed; SET only when both ends valid |
| `coolant_leak` | 0/1 | PCB AIN (1 = leak) |
| `coolant_level` | 0/1 | PCB DIN (1 = OK) |
| `coolant_flow_lpm` | L/min | Estimated from pump duty + topology multiplier |
| `fan_rpm_{i}` | RPM | Pulse tach × 30 (0-based index) |
| `pwm_duty_pump_{i}` / `pwm_duty_fan_{i}` | 0–1000 | PWM duty readback (0-based index) |
| `air_temp` / `air_humit` | °C / %RH | DHT11 or HDC302x (Pi I²C/GPIO) |
| `chassis_stabil` | 0/1 | MPU6050 (dg5w only) |
| `comm_status` | ok/timeout/disconnected | PCB Modbus health |
| `comm_consecutive_failures` | count | Rolling failure counter |
| `host_stat` | 0/1 | Host TTL key presence (USB gadget link) |

## Installation

```bash
# Dependencies (Raspbian 12)
sudo apt install -y redis-server python3-pip nodejs npm
sudo pip3 install pymodbus pyserial redis pyyaml jsons rich \
                  prometheus_client adafruit-circuitpython-dht \
                  adafruit-circuitpython-hdc302x mpu6050-raspberrypi numpy

# Clone
git clone https://github.com/<owner>/gadgetini.git /home/gadgetini/gadgetini
cd /home/gadgetini/gadgetini

# Web UI build
cd src/gui/gadgetini-web && npm install && npm run build && cd -

# systemd units
sudo cp src/configure/daemons/gadgetini/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# USB gadget network (for host integration)
sudo bash src/configure/usb-gadget-gadgetini.sh
# On the host:
sudo bash src/configure/usb-gadget-host.sh
```

Enable and verify:

```bash
sudo systemctl enable --now redis data_crawler sensor_exporter \
                            gadgetini_ui display_pannel display_logo usb-gadget-up

systemctl status data_crawler sensor_exporter
curl -s http://localhost:9003/metrics | grep dlc_system_sensor | head
redis-cli mget coolant_temp_inlet1 coolant_leak comm_status
```

## Configuration

- [src/exporter/pcb_config.yaml](src/exporter/pcb_config.yaml) — Modbus port/baud, slave id, initial PWM duty, fan curve, wiring map (PCB hw)
- [src/exporter/machine_config.py](src/exporter/machine_config.py) — machine type + coolant channel maps (legacy ADS1256 and PCB)
- [src/display/config.ini](src/display/config.ini) — TFT layout, product name/counts
- [CLAUDE.md](CLAUDE.md) — high-level architecture, dev commands

## License (TBD)

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)
[![GPLv3 License](https://img.shields.io/badge/License-GPL%20v3-yellow.svg)](https://opensource.org/licenses/)
[![AGPL License](https://img.shields.io/badge/license-AGPL-blue.svg)](http://www.gnu.org/licenses/agpl-3.0)
