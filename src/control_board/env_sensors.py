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


# ──────────────────────────────────────────────
# === aiexpo dummy block — DO NOT MERGE TO main ===
# 행사 데모용. GPU 평균 온도 → chassis air_temp/humit 추정.
# 가정: 상온 향온향습(22°C/50%RH baseline) + 액체냉각으로 부하 시 미세 상승.
# ──────────────────────────────────────────────
import random
import sys as _sys
_sys.path.insert(0, '/home/gadgetini/gadgetini/src/exporter')
from machine_config import GPU_COUNT

_DUMMY = {'t': 22.0, 'h': 33.0}
_GPU_IDLE, _GPU_LOAD = 35.0, 70.0
_AIR_BASE, _AIR_PEAK = 22.0, 25.0
_RH_BASE, _HUM_SLOPE = 33.0, -0.7   # baseline 33%RH (실측 행사장 습도)
_ALPHA = 0.05
_NOISE_T, _NOISE_H = 0.08, 0.20
_T_CLAMP = (21.5, 25.5)
_H_CLAMP = (28.0, 36.0)
_last_step_monotonic = 0.0


def _read_gpu_avg(rd):
    vals = []
    for i in range(GPU_COUNT):
        try:
            v = float(rd.get(f'gpu_temp_{i}'))
            if 5.0 < v < 110.0:
                vals.append(v)
        except (TypeError, ValueError):
            pass
    return sum(vals) / len(vals) if vals else None


def _step_dummy(rd):
    """Cycle당 1회만 EMA step. air_temp/humit 두 함수가 같은 cycle에서 호출돼도 한 번만 갱신."""
    global _last_step_monotonic
    now = time.monotonic()
    if now - _last_step_monotonic < 0.3:
        return
    _last_step_monotonic = now
    gpu_avg = _read_gpu_avg(rd)
    if gpu_avg is None:
        target_t = _AIR_BASE
    else:
        slope = (_AIR_PEAK - _AIR_BASE) / (_GPU_LOAD - _GPU_IDLE)
        target_t = max(21.5, min(25.5, _AIR_BASE + slope * (gpu_avg - _GPU_IDLE)))
    target_h = max(29.0, min(34.0, _RH_BASE + _HUM_SLOPE * (target_t - _AIR_BASE)))
    _DUMMY['t'] = (1 - _ALPHA) * _DUMMY['t'] + _ALPHA * target_t + random.gauss(0, _NOISE_T)
    _DUMMY['h'] = (1 - _ALPHA) * _DUMMY['h'] + _ALPHA * target_h + random.gauss(0, _NOISE_H)


def get_air_temp_dummy(rd):
    _step_dummy(rd)
    return round(max(_T_CLAMP[0], min(_T_CLAMP[1], _DUMMY['t'])), 1)


def get_air_humit_dummy(rd):
    _step_dummy(rd)
    return round(max(_H_CLAMP[0], min(_H_CLAMP[1], _DUMMY['h'])), 1)
