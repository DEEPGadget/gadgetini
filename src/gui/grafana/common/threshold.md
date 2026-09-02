Item	Normal	Warning	Critical
Coolant Temperature - Inlet 1/2 (°C)	22~40°C	41~45°C / 18~21°C (ASHRAE dew point path reference required)	>45°C / <18°C
Coolant Temperature - Outlet 1/2 (°C) [pg25 managed temp]	≤60°C	60~65°C / 18~21°C	>65°C / <18°C
Coolant Delta Value 1/2 (°C)	≤15°C	15~20°C	>20°C
Coolant Level	HIGH	MIDDLE	-
Coolant Leakage	NORMAL	-	LEAKED
Chassis Temperature (°C)	≤40°C	40~50°C	>50°C
Chassis Humidity (%)	10~60%	60~80%	>80%
Multi AI Processors - Temperature (°C)	≤75°C	75~90°C	>90°C
Multi AI Processors - Memory Utilization (%)	0–100%	-	-
Multi AI Processors - Core Utilization (%)	0–100%	-	-
Multi CPUs - Temperature (°C)	≤85°C	86–95°C	>95°C
Multi CPUs - Core Utilization (%)	0–100%	-	-
Available Memory (%)	≥20%	10–19%	<10%
Network – Link Status	UP (green) / DOWN (red)	-	-
Network - Infiniband NIC chipset temperature (°C)	≤105°C	105~115°C	>115°C
Server - alive status	Online (green) / Offline (red)	-	-

## Where the temperature ceilings come from

Each Critical ceiling is the limit of the most heat-sensitive part in that metric's path,
not a round number. The SoCs (AI processor, CPU, NIC) tolerate more than the parts below,
so they are never the binding constraint on the cooling curve.

- **Chassis Temperature >50°C** — the DHT11 air sensor's own operating range is 0~50°C.
  Past it the reading is out of spec, so the alert has to fire before the measurement
  itself stops being trustworthy. The air sensor is auto-detected
  (HDC302x → AHT20 → DHT11, see `src/exporter/dlc_sensors.py`); 50°C anchors on DHT11,
  the narrowest-range part supported, so the threshold stays valid on units that fall
  through to it.
- **Coolant Outlet >65°C** — the PMP500 pump's allowable coolant temperature is 60~75°C.
  65°C is the conservative end of that band.
- **Coolant Inlet >45°C** — the cold side, well below the pump's allowance.

The low-side bounds (`<18°C`, and the 18~21°C warning band) are a condensation concern,
not a part limit: they need a dew-point reference, which is still outstanding — see the
`ASHRAE dew point path reference required` note on the inlet row.

These ceilings are consumed as the `max_temp` fan-curve anchors in
`src/exporter/pcb_config.yaml` (factory values in `src/exporter/pcb_defaults.yaml`).
Change a value here and those must be revisited with it — `src/exporter/pcb_control.py`
carries the matching rationale in its module docstring.
