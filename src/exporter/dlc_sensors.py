#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Pi 직결 센서 — ADS1256(coolant, legacy 한정) + 환경(HDC302x/DHT11) + MPU6050.

ADS1256 init은 graceful: 미장착(PCB 머신)이면 _ADC_AVAILABLE=False 로 두고 import
단계에서 죽지 않는다. _ADC_AVAILABLE 은 백엔드 family discriminator로도 쓰인다
(True=legacy Gen1~2, False=PCB Gen3 → pcb_driver.detect_backend 참고).

env(air_temp/humit)·chassis(MPU6050)는 Pi 직결이라 메인보드/PCB 전원과 무관하게
**양 백엔드 공통·상시** 센싱된다 (Rev_C에서 PCB OFF여도 온/습도는 계속 수집).
"""
import math
import sys
import time

from machine_config import MACHINE, COOLANT_CHANNELS

try:
    import numpy as np
    _HAS_NP = True
except Exception:
    _HAS_NP = False


def _median(samples):
    if not samples:
        return None
    if _HAS_NP:
        return float(np.median(samples))
    s = sorted(samples)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


# ──────────────────────────────────────────────────────────────────
# ADS1256 (coolant, legacy 한정) — graceful fallback
# ──────────────────────────────────────────────────────────────────
try:
    sys.path.append('/home/gadgetini/High-Precision-AD-DA-Board-Code/RaspberryPI/ADS1256/python3')
    import ADS1256 as _ads_lib
    _ADC = _ads_lib.ADS1256()
    _ADC.ADS1256_init()
    _ADC_AVAILABLE = True
except Exception as e:
    print(f"ADS1256 init failed (OK if PCB present): {e}")
    _ADC = None
    _ADC_AVAILABLE = False


def _collect_adc_samples(n=30):
    return [_ADC.ADS1256_GetAll() for _ in range(n)]


def get_coolant_temp(ad_index, adc_samples=None):
    if not _ADC_AVAILABLE:
        return None
    VREF = 5.0
    VIN_DIV = 3.3
    R_FIXED = 10000.0
    SH_A = 0.0010957
    SH_B = 0.0002395
    SH_C = 0.000000073454
    try:
        if adc_samples is None:
            adc_samples = _collect_adc_samples()
        vs = [float(s[ad_index]) * VREF / 0x7fffff for s in adc_samples]
        vout = float(_median(vs))
        # Voltage pinned to either rail → NTC not connected on this channel.
        if vout <= 0.001 or vout >= (VIN_DIV - 0.05):
            return None
        r_ntc = (vout * R_FIXED) / (VIN_DIV - vout)
        ln_r = math.log(r_ntc)
        temp_k = 1.0 / (SH_A + (SH_B * ln_r) + (SH_C * (ln_r ** 3)))
        return round(temp_k - 273.15, 1)
    except Exception:
        return None


def get_coolant_leak_detection(adc_samples=None):
    if not _ADC_AVAILABLE:
        return None
    if adc_samples is None:
        adc_samples = _collect_adc_samples()
    samples = [round(float(s[7] * 5.0 / 0x7fffff), 3) for s in adc_samples]
    return 1 if float(_median(samples)) < 3.0 else 0


def get_coolant_level_detection(adc_samples=None):
    if not _ADC_AVAILABLE:
        return None
    if adc_samples is None:
        adc_samples = _collect_adc_samples()
    samples = [round(float(s[6] * 5.0 / 0x7fffff), 3) for s in adc_samples]
    return 0 if float(_median(samples)) > 1.2 else 1


# ──────────────────────────────────────────────────────────────────
# 온/습도 — HDC302x 우선 (I2C deterministic), fallback DHT11. 양 백엔드 공통.
# ──────────────────────────────────────────────────────────────────
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
    # GPIO 셋업만 검증. DHT11 read는 본래 flaky해서 probe 단계에서 read 성공을
    # 요구하면 startup 운에 따라 영구적으로 None에 갇힘. 런타임 retry는 get_*에서.
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
print(f"Temp/humid sensor: {_temp_humid_kind or 'none'}")


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


# ──────────────────────────────────────────────────────────────────
# 자이로 — MPU6050 (dg5w 한정). 양 백엔드 공통 (Rev_D에서 PCB 이관 예정).
# ──────────────────────────────────────────────────────────────────
_gyro_dev = None
if MACHINE == 'dg5w':
    try:
        import mpu6050 as _gyro_mod
        _gyro_dev = _gyro_mod.mpu6050(0x68)
    except Exception as e:
        print(f"Gyro (MPU6050) init failed, chassis stability will report stable: {e}")
        _gyro_dev = None


def get_chassis_stabil():
    """1=stable, 0=unstable, None=non-dg5w (caller가 SET 생략)."""
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


# ──────────────────────────────────────────────────────────────────
# Entry 함수 — data_crawler.py가 호출
# ──────────────────────────────────────────────────────────────────
def poll_coolant(rd):
    """ADS1256으로 coolant_temp_*, delta_t, leak, level 일괄 read + Redis SET.

    Legacy hw 한정. _ADC_AVAILABLE False면 no-op (PCB 경로에선 어차피 호출 안 됨).
    """
    if not _ADC_AVAILABLE:
        return
    adc = _collect_adc_samples()
    channels = COOLANT_CHANNELS.get(MACHINE, {})
    pipe = rd.pipeline(transaction=False)

    temps = {}
    for name, idx in channels.items():
        temp = get_coolant_temp(idx, adc)
        temps[name] = temp
        key = f"coolant_temp_{name}"
        if temp is None:
            pipe.delete(key)
        else:
            pipe.set(key, temp)

    def _delta_or_clear(in_name, out_name, key):
        i, o = temps.get(in_name), temps.get(out_name)
        if i is not None and o is not None:
            pipe.set(key, round(o - i, 2))
        else:
            pipe.delete(key)

    _delta_or_clear('inlet1', 'outlet1', 'coolant_delta_t1')
    _delta_or_clear('inlet2', 'outlet2', 'coolant_delta_t2')

    leak = get_coolant_leak_detection(adc)
    if leak is not None:
        pipe.set("coolant_leak", leak)
    level = get_coolant_level_detection(adc)
    if level is not None:
        pipe.set("coolant_level", level)
    pipe.execute()


def update_env(rd):
    """HDC302x/DHT11으로 air_temp, air_humit Redis SET. 양 백엔드 공통 (Pi-side 상시)."""
    t = get_air_temp()
    if t is not None:
        rd.set("air_temp", round(t, 1))
    h = get_air_humit()
    if h is not None:
        rd.set("air_humit", round(h, 1))


def update_chassis(rd):
    """MPU6050으로 chassis_stabil Redis SET. dg5w 한정 (None이면 생략)."""
    stabil = get_chassis_stabil()
    if stabil is not None:
        rd.set("chassis_stabil", stabil)
