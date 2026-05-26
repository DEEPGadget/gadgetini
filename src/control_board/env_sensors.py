"""Environment sensors read directly from the RPi - HDC302x/DHT11 auto-detect + MPU6050 stub.

Sensors connected directly to the host, independent of PCB communication. All init/read
calls are wrapped in try/except for graceful degradation - no matter the cause (chip not
installed, library missing, comm failure), import never dies and fail-safe values are
returned (same pattern as dlc_sensors.py).
"""
import configparser
import time

try:
    import numpy as np
    _HAS_NP = True
except Exception:
    _HAS_NP = False


# ==============================================
# Machine identification - single source of truth is display/config.ini (same as machine_config.py)
# ==============================================
def _detect_machine():
    try:
        cfg = configparser.ConfigParser()
        cfg.read('/home/gadgetini/gadgetini/src/display/config.ini')
        return cfg.get('PRODUCT', 'name', fallback='unknown').lower()
    except Exception:
        return 'unknown'


MACHINE = _detect_machine()


# ==============================================
# Temperature/humidity - prefer HDC302x (I2C deterministic), fallback to DHT11
# ==============================================

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
    # Only verify GPIO setup. DHT11 reads are inherently flaky, so if we require a successful
    # read at probe time, startup luck could lock us into None forever and the key would never
    # be set. Runtime reads retry internally in get_air_temp/humit.
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


# ==============================================
# Gyro - MPU6050 (dg5w only, effectively unused)
# ==============================================

_gyro_dev = None
if MACHINE == 'dg5w':
    try:
        import mpu6050 as _gyro_mod
        _gyro_dev = _gyro_mod.mpu6050(0x68)
    except Exception:
        _gyro_dev = None


def get_chassis_stabil():
    """1=stable, 0=unstable, None=non-dg5w (caller skips the SET).

    dg5w only. Fail-safe returns 1 on init or read failure.
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
