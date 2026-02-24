#!/usr/bin/python3
# -*- coding: utf-8 -*-
import sys
sys.path.append('/home/gadgetini/High-Precision-AD-DA-Board-Code/RaspberryPI/ADS1256/python3')
import configparser
import ADS1256
import math
import numpy as np
import adafruit_dht
import board
import time

_config = configparser.ConfigParser()
_config.read('/home/gadgetini/gadgetini/src/display/config.ini')
MACHINE = _config.get('PRODUCT', 'name', fallback='unknown').lower()

# dg5r: inlet1=ad2, outlet1=ad3, outlet2=ad4, inlet2=ad5
# dg5w: inlet1=ad4
COOLANT_CHANNELS = {
    'dg5r': {'inlet1': 2, 'outlet1': 3, 'outlet2': 4, 'inlet2': 5},
    'dg5w': {'inlet1': 4},
}

ADC = ADS1256.ADS1256()
ADC.ADS1256_init()
dhtDevice = adafruit_dht.DHT11(board.D4)

if MACHINE == 'dg5w':
    import mpu6050 as gyro
    gyroDevice = gyro.mpu6050(0x68)


def _collect_adc_samples(n=30):
    return [ADC.ADS1256_GetAll() for _ in range(n)]


def get_air_temp():
    samples = []
    for _ in range(5):
        try:
            v = dhtDevice.temperature
            if v is not None:
                samples.append(v)
        except Exception:
            pass
    return float(np.median(samples)) if samples else 0.0


def get_air_humit():
    samples = []
    for _ in range(5):
        try:
            v = dhtDevice.humidity
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

        if vout <= 0.001 or vout >= (VIN_DIV - 0.001):
            return 0

        r_ntc = (vout * R_FIXED) / (VIN_DIV - vout)
        ln_r = math.log(r_ntc)
        temp_k = 1.0 / (SH_A + (SH_B * ln_r) + (SH_C * (ln_r ** 3)))
        return round(temp_k - 273.15, 1)

    except Exception:
        return 0


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
