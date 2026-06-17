import configparser

_cfg = configparser.ConfigParser()
_cfg.read('/home/gadgetini/gadgetini/src/display/config.ini')

MACHINE = _cfg.get('PRODUCT', 'name', fallback='unknown').lower()
GPU_COUNT = _cfg.getint('PRODUCT', 'gpu_count', fallback=8)
CPU_COUNT = _cfg.getint('PRODUCT', 'cpu_count', fallback=2)

# Legacy ADS1256 채널 매핑 (Gen1~2, ADS1256 직결)
# dg5r: inlet1=ad2, outlet1=ad3, outlet2=ad4, inlet2=ad5
# dg5w: inlet1=ad4, outlet1=ad5 (older units may not have outlet1 wired;
#       disconnected NTC is auto-detected at the sensor layer and the key is omitted)
COOLANT_CHANNELS = {
    'dg5r': {'inlet1': 2, 'outlet1': 3, 'outlet2': 4, 'inlet2': 5},
    'dg5w': {'inlet1': 4, 'outlet1': 5},
}

# PCB Modbus NTC 채널 매핑 (Gen3, 제어보드). PCB NTC 입력은 CH13~16 (IR 28~31).
# config.ini의 machine 타입이 진실의 source — dict 선언이 곧 wiring 명세.
COOLANT_CHANNELS_PCB = {
    'dg5r': {'inlet1': 13, 'outlet1': 14, 'outlet2': 15, 'inlet2': 16},
    'dg5w': {'inlet1': 13, 'outlet1': 14},
}

# Prometheus `server` label. Lowercase to match Grafana dashboard queries
# (dlc_system_sensor{server="dg5w"} / "dg5r").
MACHINE_LABEL = MACHINE
