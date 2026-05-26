#!/usr/bin/python3
# -*- coding: utf-8 -*-
import sys
sys.path.append('/home/gadgetini/High-Precision-AD-DA-Board-Code/RaspberryPI/ADS1256/python3')
import ADS1256
import math
import numpy as np
import board
import time
from machine_config import MACHINE, COOLANT_CHANNELS

ADC = ADS1256.ADS1256()
ADC.ADS1256_init()


def _probe_hdc302x():
    try:
        import busio
        import adafruit_hdc302x
        i2c = busio.I2C(board.SCL, board.SDA)
        dev = adafruit_hdc302x.HDC302x(i2c)
        _ = dev.temperature
        return dev
    except Exception:
        return None


def _probe_dht11():
    # Only verify the GPIO setup. DHT11 reads are inherently flaky, so if we
    # require a successful read at probe time, bad startup luck can leave us
    # permanently stuck on None and pin the value at 0.
    # Runtime reads retry on their own inside get_air_temp/humit.
    try:
        import adafruit_dht
        return adafruit_dht.DHT11(board.D4)
    except Exception:
        return None


# Try HDC302x first (I2C is deterministic). Fall back to DHT11 if not present.
tempHumidDevice = _probe_hdc302x()
tempHumidType = 'hdc302x' if tempHumidDevice is not None else None
if tempHumidDevice is None:
    tempHumidDevice = _probe_dht11()
    tempHumidType = 'dht11' if tempHumidDevice is not None else None
print(f"Temp/humid sensor: {tempHumidType or 'none'}")


gyroDevice = None
if MACHINE == 'dg5w':
    try:
        import mpu6050 as gyro
        gyroDevice = gyro.mpu6050(0x68)
    except Exception as e:
        print(f"Gyro (MPU6050) init failed, chassis stability will report stable: {e}")
        gyroDevice = None


def _collect_adc_samples(n=30):
    return [ADC.ADS1256_GetAll() for _ in range(n)]


def _read_temp_once():
    if tempHumidDevice is None:
        return None
    return tempHumidDevice.temperature


def _read_humid_once():
    if tempHumidDevice is None:
        return None
    if tempHumidType == 'dht11':
        return tempHumidDevice.humidity
    return tempHumidDevice.relative_humidity


def get_air_temp():
    if tempHumidDevice is None:
        return 0.0
    samples = []
    for _ in range(5):
        try:
            v = _read_temp_once()
            if v is not None:
                samples.append(v)
        except Exception:
            pass
    return float(np.median(samples)) if samples else 0.0


def get_air_humit():
    if tempHumidDevice is None:
        return 0.0
    samples = []
    for _ in range(5):
        try:
            v = _read_humid_once()
            if v is not None:
                samples.append(v)
        except Exception:
            pass
    return float(np.median(samples)) if samples else 0.0


def get_coolant_temp(ad_index, adc_samples=None):
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
        vout = float(np.median(vs))

        # Voltage pinned to either rail → NTC not connected on this channel.
        # Return None so the caller can omit the key entirely (vs reporting a fake 0°C).
        if vout <= 0.001 or vout >= (VIN_DIV - 0.05):
            return None

        r_ntc = (vout * R_FIXED) / (VIN_DIV - vout)
        ln_r = math.log(r_ntc)
        temp_k = 1.0 / (SH_A + (SH_B * ln_r) + (SH_C * (ln_r ** 3)))
        return round(temp_k - 273.15, 1)

    except Exception:
        return None


def get_coolant_leak_detection(adc_samples=None):
    if adc_samples is None:
        adc_samples = _collect_adc_samples()
    samples = [round(float(s[7] * 5.0 / 0x7fffff), 3) for s in adc_samples]
    return 1 if float(np.median(samples)) < 3.0 else 0


def get_coolant_level_detection(adc_samples=None):
    if adc_samples is None:
        adc_samples = _collect_adc_samples()
    samples = [round(float(s[6] * 5.0 / 0x7fffff), 3) for s in adc_samples]
    return 0 if float(np.median(samples)) > 1.2 else 1


def get_chassis_stabil():
    if MACHINE != 'dg5w':
        return None
    if gyroDevice is None:
        return 1
    try:
        current = gyroDevice.get_gyro_data()
        curr_x = current['x']
        curr_y = current['y']
        curr_z = current['z']
        time.sleep(0.01)
        init = gyroDevice.get_gyro_data()
        init_x = init['x']
        init_y = init['y']
        init_z = init['z']
        if abs(curr_x - init_x) > 5 and abs(curr_y - init_y) > 5 or abs(curr_z - init_z) > 5:
            return 0
        return 1
    except Exception:
        return 1
