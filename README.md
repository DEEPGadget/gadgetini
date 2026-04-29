# gadgetini

gadgetini is a server monitoring system specialized for Direct Liquid Cooling (DLC) systems in [DeepGadget](https://deepgadget.com/) servers (dg5w / dg5r). It collects DLC sensor data on a Raspberry Pi 4 B+, drives a physical TFT status display, runs a closed-loop fan/pump controller via a custom RS485 PCB, and exposes Prometheus metrics + a Next.js configuration web UI.

![manycore_logo_black (3)](https://github.com/user-attachments/assets/2e65773a-b1cc-46ee-8831-7d3d95a5b798)

## Architecture

```
 HOST (dg5W)              GADGETINI (Raspberry Pi 4)
                          ┌─────────────────────────────────────────────┐
┌──────────────┐          │ ┌──────────┐    ┌──────────────┐           │
│data_crawler_ │─USB Net─▶│ │          │◀───│ control_board│◀ RS485 ──┼── PCB (Modbus RTU)
│host.py       │ TCP/IPv6 │ │  Redis   │    │  (PCB hw)    │           │   NTC × 4, leak, level,
│(CPU/GPU/NIC) │          │ │          │    │   OR         │           │   pump/fan PWM, tach
└──────────────┘          │ │          │    │ data_crawler │◀ I2C/SPI ─┼── ADS1256 (legacy hw)
                          │ └────┬─────┘    │  (legacy hw) │           │
                          │      │          └──────────────┘           │
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

**Two collector paths, mutually exclusive:**

- **New hw (PCB present)** — `pcb_bootstrap.service` probes Modbus on `/dev/serial0` and `/dev/ttyUSB0` at boot. On detection it starts `control_board.service`, which polls the PCB, drives the fan curve, and writes sensor values into Redis.
- **Legacy hw (no PCB)** — `data_crawler.service` runs the original ADS1256 + I2C path. `control_board.service`'s `Conflicts=` ensures only one collector runs.

### Boot sequence (collector selection)

```
                          systemd boot (multi-user.target)
                                        │
                                        ▼
                          ┌───────────────────────────┐
                          │ pcb_bootstrap.service     │  oneshot, RemainAfterExit=yes
                          │  Type=oneshot, runs once  │  Before= sensor_exporter,
                          │                           │           data_crawler,
                          │                           │           display_pannel
                          └─────────────┬─────────────┘
                                        │
                          probe Modbus RTU on each port × baud:
                            /dev/serial0  @ 115200, 9600
                            /dev/ttyUSB0  @ 115200, 9600
                                        │
                       ┌────────────────┴────────────────┐
                       │                                 │
                first probe OK                     all probes fail
                       │                                 │
                       ▼                                 ▼
        ┌──────────────────────────┐       ┌──────────────────────────┐
        │ systemctl start          │       │ exit 0 (no-op)           │
        │   control_board.service  │       │                          │
        │                          │       │ data_crawler.service     │
        │  Conflicts=              │       │ runs via its own         │
        │   data_crawler.service   │       │ [Install] WantedBy=      │
        │  → systemd auto-stops    │       │   multi-user.target      │
        │     data_crawler if it   │       │                          │
        │     was started          │       │                          │
        └────────────┬─────────────┘       └────────────┬─────────────┘
                     │                                  │
                     ▼                                  ▼
        ┌──────────────────────────┐       ┌──────────────────────────┐
        │ control_board.main       │       │ data_crawler.py          │
        │  • baud-list fallback    │       │  (ADS1256 + I²C/GPIO)    │
        │    (config.yaml)         │       │                          │
        │  • PWM init + fan curve  │       │                          │
        │  • Modbus poll → Redis   │       │                          │
        └────────────┬─────────────┘       └────────────┬─────────────┘
                     │                                  │
                     └─────────────► Redis ◄────────────┘
                                       │
                              ┌────────┴────────┐
                              ▼                 ▼
                        sensor_exporter    display_pannel
                          (:9003)            (TFT loop)
```

**Bootstrap behavior** ([src/control_board/pcb_bootstrap.py](src/control_board/pcb_bootstrap.py)):

- Always exits 0 — boot is never blocked by detection failure.
- Decision is one-shot per boot. If the PCB is connected after boot, `pcb_bootstrap.service` must be restarted manually (`sudo systemctl restart pcb_bootstrap.service`) — bootstrap re-probes and starts `control_board.service` on success, which in turn auto-stops `data_crawler.service` via `Conflicts=`.
- Two layers of baud fallback for resilience: bootstrap probes `[115200, 9600]` to decide which collector to start, and `control_board.main` does the same when establishing its own session — so a board running at the non-default baud still connects without config edits.

Detail: see [src/control_board/README.md](src/control_board/README.md).

## Hardware

- **Compute**: Raspberry Pi 4 B+ (Raspbian 12 bookworm)
- **PCB control board** (new hw): isolated RS485 Modbus RTU, 12 PWM channels (TIM1 1 kHz pump × 4, TIM2 25 kHz fan × 4, TIM8 25 kHz fan × 4), pulse tach inputs, 16-channel ADC, 8 DIN
- **Display**: Adafruit 1.9" 320×170 ST7789 TFT
- **Cooling sensors**: 10k NTC × 4 (inlet1/outlet1/inlet2/outlet2), liquid leak (AIN), liquid level (DIN), waterflow (estimated from pump duty)
- **Environment sensors**: DHT11 or HDC302x (auto-detect, RPi I²C direct), MPU6050 gyro for chassis stability (dg5w only)
- **Legacy ADC** (no-PCB hw only): Waveshare High-Precision AD/DA (ADS1256)

## Services

All systemd units in [src/configure/daemons/gadgetini/](src/configure/daemons/gadgetini/):

| Service | Type | Purpose |
|---|---|---|
| `redis.service` | always-on | Sensor cache + pub/sub |
| `pcb_bootstrap.service` | oneshot | Probes PCB at boot, starts `control_board.service` if detected |
| `control_board.service` | new hw | Modbus polling, fan curve, Redis publish |
| `data_crawler.service` | legacy hw | ADS1256 + I²C polling. Conflicts with `control_board.service` |
| `sensor_exporter.service` | always-on | Prometheus endpoint on `:9003` |
| `gadgetini_ui.service` | always-on | Next.js config UI on `:3001` |
| `display_pannel.service` | always-on | TFT live status loop |
| `display_logo.service` | oneshot | Boot splash on TFT |
| `usb-gadget-up.service` | oneshot | NetworkManager up for USB gadget link to host |

PCB collector lifecycle: `pcb_bootstrap` runs once at boot → probes both ports × both bauds (115200, 9600) → starts `control_board.service` on detection or exits cleanly. `control_board` itself also retries port/baud combinations from [config.yaml](src/control_board/config.yaml), so a board running at the non-default baud still connects without manual intervention.

## Redis Keys

Flat naming, consumed by `sensor_exporter`:

| Key | Unit | Source |
|---|---|---|
| `coolant_temp_inlet1` / `inlet2` | °C | NTC via PCB IR 28 / IR 31 |
| `coolant_temp_outlet1` / `outlet2` | °C | NTC via PCB IR 29 / IR 30 |
| `coolant_delta_t1` / `delta_t2` | °C | Computed; SET only when both ends valid |
| `coolant_leak` | 0/1 | PCB AIN CH8 (1 = leak) |
| `coolant_level` | 0/1 | PCB DIN2 (1 = OK) |
| `coolant_flow_lpm` | L/min | Estimated from pump duty + topology multiplier |
| `fan_rpm_1` / `fan_rpm_2` | RPM | Pulse CH9 / CH10 × 30 (Cooltron 2 p/r) |
| `pump_rpm` | RPM | Pulse from pump tach lead |
| `air_temp` / `air_humit` | °C / %RH | DHT11 or HDC302x (RPi I²C) |
| `chassis_stabil` | 0/1 | MPU6050 (dg5w only) |
| `comm_status` | ok/timeout/disconnected | PCB Modbus health |
| `comm_consecutive_failures` | count | Rolling failure counter |
| `host_stat` | 0/1 | Host TTL (USB gadget link) |

## Installation

```bash
# Dependencies (Raspbian 12)
sudo apt install -y redis-server python3-pip nodejs npm
sudo pip3 install pymodbus pyserial-asyncio redis pyyaml jsons rich \
                  prometheus_client adafruit-circuitpython-dht \
                  adafruit-circuitpython-hdc302x adafruit-circuitpython-mpu6050

# Clone and install
git clone https://github.com/<owner>/gadgetini.git /home/gadgetini/gadgetini
cd /home/gadgetini/gadgetini

# Web UI build
cd src/gui/gadgetini-web && npm install && npm run build && cd -

# Systemd units (PCB-based hw)
sudo bash src/control_board/install.sh

# USB gadget network (for host integration)
sudo bash src/configure/usb-gadget-gadgetini.sh
# On the host:
sudo bash src/configure/usb-gadget-host.sh
```

After install:

```bash
sudo systemctl enable --now redis pcb_bootstrap sensor_exporter \
                            gadgetini_ui display_pannel display_logo
# control_board is started by pcb_bootstrap on detection; do not enable it directly.

# Verify
systemctl status pcb_bootstrap control_board sensor_exporter
curl -s http://localhost:9003/metrics | grep dlc_system_sensor | head
redis-cli mget coolant_temp_inlet1 coolant_leak comm_status
```

## Configuration

- [src/control_board/config.yaml](src/control_board/config.yaml) — Modbus port/baud, slave id, initial PWM duty, fan curve, wiring map, threshold
- [src/display/config.ini](src/display/config.ini) — TFT layout
- [CLAUDE.md](CLAUDE.md) — high-level architecture, dev commands

## Roadmap

- Phase 1 (DONE): control_board logic, fan curve hysteresis, Modbus baud fallback, PCB auto-detect bootstrap
- Phase 2 (in progress): integration verification — pump flow multiplier calibration, fan RPM data-sheet match, closed-loop fan curve under thermal load, RS485 disconnect → `comm_status` transitions, full reboot bootstrap flow
- Phase 3: ΔT-cascade pump control after a flow meter is fitted; emergency stop / Grafana alert rules

## License (TBD)

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)
[![GPLv3 License](https://img.shields.io/badge/License-GPL%20v3-yellow.svg)](https://opensource.org/licenses/)
[![AGPL License](https://img.shields.io/badge/license-AGPL-blue.svg)](http://www.gnu.org/licenses/agpl-3.0)
