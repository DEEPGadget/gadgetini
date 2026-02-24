import configparser

_cfg = configparser.ConfigParser()
_cfg.read('/home/gadgetini/gadgetini/src/display/config.ini')

MACHINE = _cfg.get('PRODUCT', 'name', fallback='unknown').lower()

# dg5r: inlet1=ad2, outlet1=ad3, outlet2=ad4, inlet2=ad5
# dg5w: inlet1=ad4 (outlet 채널 확장 시 여기에 추가, delta_t는 자동으로 계산됨)
COOLANT_CHANNELS = {
    'dg5r': {'inlet1': 2, 'outlet1': 3, 'outlet2': 4, 'inlet2': 5},
    'dg5w': {'inlet1': 4},
}
