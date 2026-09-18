import configparser

_cfg = configparser.ConfigParser()
_cfg.read('/home/gadgetini/gadgetini/src/display/config.ini')

# Canonical product names. config.ini is matched case-insensitively so units
# still carrying the older lowercase `name=dg5w` keep resolving.
PRODUCTS = ('dg5W', 'dg5R')

_name = _cfg.get('PRODUCT', 'name', fallback='unknown').strip()
MACHINE = next((p for p in PRODUCTS if p.lower() == _name.lower()), _name)
GPU_COUNT = _cfg.getint('PRODUCT', 'gpu_count', fallback=8)
CPU_COUNT = _cfg.getint('PRODUCT', 'cpu_count', fallback=2)

# Legacy ADS1256 channel map (Gen1~2, ADS1256 direct).
# dg5R: inlet1=ad2, outlet1=ad3, outlet2=ad4, inlet2=ad5
# dg5W: inlet1=ad4, outlet1=ad5 (older units may not have outlet1 wired;
#       disconnected NTC is auto-detected at the sensor layer and the key is omitted)
COOLANT_CHANNELS = {
    'dg5R': {'inlet1': 2, 'outlet1': 3, 'outlet2': 4, 'inlet2': 5},
    'dg5W': {'inlet1': 4, 'outlet1': 5},
}

# PCB Modbus NTC channel map (Gen3 control board). NTC inputs are CH13~16 (IR 28~31).
# config.ini machine type is the source of truth; this dict is the wiring spec.
COOLANT_CHANNELS_PCB = {
    'dg5R': {'inlet1': 13, 'outlet1': 14, 'outlet2': 15, 'inlet2': 16},
    'dg5W': {'inlet1': 13, 'outlet1': 14},
}

# Prometheus `server` label. Canonical casing to match Grafana dashboard queries
# (dlc_system_sensor{server="dg5W"} / "dg5R").
MACHINE_LABEL = MACHINE
