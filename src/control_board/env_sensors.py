"""RPi 직접 수집 환경 센서 — HDC302x/DHT11 자동 감지 + MPU6050 stub.

PCB 통신과 별개로 호스트에 직접 연결된 센서들. 모든 init/read는 try/except로
graceful — 칩 미장착·라이브러리 미설치·통신 실패 어떤 경우에도 import 단계에서
죽지 않고 fail-safe 값을 반환한다 (dlc_sensors.py 패턴 동일).
"""
import configparser
import time

try:
    import numpy as np
    _HAS_NP = True
except Exception:
    _HAS_NP = False


# ──────────────────────────────────────────────
# Machine 식별 — display/config.ini 단일 원천 (machine_config.py와 동일)
# ──────────────────────────────────────────────
def _detect_machine():
    try:
        cfg = configparser.ConfigParser()
        cfg.read('/home/gadgetini/gadgetini/src/display/config.ini')
        return cfg.get('PRODUCT', 'name', fallback='unknown').lower()
    except Exception:
        return 'unknown'


MACHINE = _detect_machine()


# ──────────────────────────────────────────────
# 온/습도 — HDC302x 우선 (I2C deterministic), fallback DHT11
# ──────────────────────────────────────────────

def _probe_hdc302x():
    try:
        import busio, board, adafruit_hdc302x
        i2c = busio.I2C(board.SCL, board.SDA)
        dev = adafruit_hdc302x.HDC302x(i2c)
        _ = dev.temperature
        return dev
    except Exception:
        return None


def _probe_dht11():
    # GPIO 셋업만 검증. DHT11은 read가 본래 flaky해서 probe 단계에서
    # read 성공을 요구하면 startup 운에 따라 영구적으로 None에 갇혀 키가 안 박힘.
    # 런타임 read는 get_air_temp/humit에서 자체 retry함.
    try:
        import adafruit_dht, board
        return adafruit_dht.DHT11(board.D4)
    except Exception:
        return None


_temp_humid_dev = _probe_hdc302x()
_temp_humid_kind = 'hdc302x' if _temp_humid_dev is not None else None
if _temp_humid_dev is None:
    _temp_humid_dev = _probe_dht11()
    _temp_humid_kind = 'dht11' if _temp_humid_dev is not None else None


def _read_temp_once():
    if _temp_humid_dev is None:
        return None
    return _temp_humid_dev.temperature


def _read_humid_once():
    if _temp_humid_dev is None:
        return None
    if _temp_humid_kind == 'dht11':
        return _temp_humid_dev.humidity
    return _temp_humid_dev.relative_humidity


def _median(samples):
    if not samples:
        return None
    if _HAS_NP:
        return float(np.median(samples))
    s = sorted(samples)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def _read_n(read_fn, n=5):
    out = []
    for _ in range(n):
        try:
            v = read_fn()
            if v is not None:
                out.append(v)
        except Exception:
            pass
    return _median(out)


def get_air_temp():
    """°C, fail-safe None."""
    return _read_n(_read_temp_once)


def get_air_humit():
    """%RH, fail-safe None."""
    return _read_n(_read_humid_once)


def temp_humid_kind():
    return _temp_humid_kind


# ──────────────────────────────────────────────
# 자이로 — MPU6050 (dg5w 한정, 사실상 미사용)
# ──────────────────────────────────────────────

_gyro_dev = None
if MACHINE == 'dg5w':
    try:
        import mpu6050 as _gyro_mod
        _gyro_dev = _gyro_mod.mpu6050(0x68)
    except Exception:
        _gyro_dev = None


def get_chassis_stabil():
    """1=stable, 0=unstable, None=non-dg5w (caller가 SET 생략).

    dg5w 한정. init 실패·read 실패 시 fail-safe로 1.
    """
    if MACHINE != 'dg5w':
        return None
    if _gyro_dev is None:
        return 1
    try:
        a = _gyro_dev.get_gyro_data()
        time.sleep(0.01)
        b = _gyro_dev.get_gyro_data()
        if (abs(a['x'] - b['x']) > 5 and abs(a['y'] - b['y']) > 5) or abs(a['z'] - b['z']) > 5:
            return 0
        return 1
    except Exception:
        return 1
