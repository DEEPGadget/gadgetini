#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Pi-attached sensors — ADS1256 (coolant, legacy only) + DHT11/HDC302x/AHT20 + MPU6050.

ADS1256 init is graceful: when absent (PCB machine) _ADC_AVAILABLE stays False instead
of failing at import. _ADC_AVAILABLE also serves as the backend discriminator
(True = legacy Gen1~2, False = PCB Gen3; see pcb_driver.detect_backend).

Env (air temp/humidity) and chassis are Pi-attached, so they run on both backends and
keep working regardless of PCB/mainboard power.
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


# ── ADS1256 (coolant, legacy only) — graceful fallback ─────────────
try:
    sys.path.append('/home/gadgetini/High-Precision-AD-DA-Board-Code/RaspberryPI/ADS1256/python3')
    import ADS1256 as _ads_lib
    _ADC = _ads_lib.ADS1256()
    # ADS1256_init() returns -1 (it does NOT raise) when the chip ID read fails —
    # i.e. the board is absent and SPI reads garbage. Treat that as "not present"
    # so the backend discriminator doesn't false-positive to legacy on a PCB machine.
    if _ADC.ADS1256_init() != 0:
        raise RuntimeError("ADS1256_init failed (chip ID mismatch / board not present)")
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
        # Pinned to a rail = NTC not connected -> None so the caller omits the key.
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


# ── Air temp/humidity — HDC302x → AHT20 (I2C, instant) → DHT11 (catch-all). Both backends. ──
def _probe_hdc302x():
    try:
        import busio, board, adafruit_hdc302x
        i2c = busio.I2C(board.SCL, board.SDA)
        dev = adafruit_hdc302x.HDC302x(i2c)
        _ = dev.temperature
        return dev
    except Exception:
        return None


def _probe_aht20():
    # Adafruit AHT20 (#4566), I2C 0x38. Library: adafruit-circuitpython-ahtx0.
    # Exposes .temperature / .relative_humidity (same API as HDC302x).
    try:
        import busio, board, adafruit_ahtx0
        i2c = busio.I2C(board.SCL, board.SDA)
        dev = adafruit_ahtx0.AHTx0(i2c)
        _ = dev.temperature
        return dev
    except Exception:
        return None


def _probe_dht11():
    # Last-resort catch-all: DHT11 is a 1-wire GPIO sensor with no I2C address to probe,
    # so we only set up the GPIO (no read = no startup delay). Runtime reads in
    # get_air_temp/humit retry, since DHT11 reads are flaky.
    try:
        import adafruit_dht, board
        return adafruit_dht.DHT11(board.D4)
    except Exception:
        return None


# Detection order: HDC302x (I2C 0x44) → AHT20 (I2C 0x38) → DHT11 (GPIO, catch-all).
# I2C sensors are detected instantly by address, so an absent one is skipped with no
# delay. DHT11 has no address (can't be quick-probed), so it is the last fallback.
# A machine carries exactly one of these sensors → order only affects speed, not which
# sensor wins.
_temp_humid_dev = _probe_hdc302x()
_temp_humid_kind = 'hdc302x' if _temp_humid_dev is not None else None
if _temp_humid_dev is None:
    _temp_humid_dev = _probe_aht20()
    _temp_humid_kind = 'aht20' if _temp_humid_dev is not None else None
if _temp_humid_dev is None:
    _temp_humid_dev = _probe_dht11()
    _temp_humid_kind = 'dht11' if _temp_humid_dev is not None else None
print(f"Temp/humid sensor: {_temp_humid_kind or 'none'}", flush=True)


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
    """Celsius, fail-safe None."""
    return _read_n(_read_temp_once)


def get_air_humit():
    """%RH, fail-safe None."""
    return _read_n(_read_humid_once)


# ── Gyro — MPU6050 (dg5w only). Both backends (moves to PCB on Rev_D). ──
_gyro_dev = None
if MACHINE == 'dg5w':
    try:
        import mpu6050 as _gyro_mod
        _gyro_dev = _gyro_mod.mpu6050(0x68)
    except Exception as e:
        print(f"Gyro (MPU6050) init failed, chassis stability will report stable: {e}")
        _gyro_dev = None


def get_chassis_stabil():
    """1=stable, 0=unstable, None=non-dg5w (caller omits the key)."""
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


# ── Entry points called by data_crawler.py ─────────────────────────
def poll_coolant(rd):
    """ADS1256 -> coolant_temp_*, delta_t, leak, level. Legacy only; no-op without ADC."""
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
    """air_temp, air_humit -> Redis. Both backends (Pi-attached, always-on)."""
    t = get_air_temp()
    if t is not None:
        rd.set("air_temp", round(t, 1))
    h = get_air_humit()
    if h is not None:
        rd.set("air_humit", round(h, 1))


def update_chassis(rd):
    """chassis_stabil -> Redis. dg5w only (None is skipped)."""
    stabil = get_chassis_stabil()
    if stabil is not None:
        rd.set("chassis_stabil", stabil)
