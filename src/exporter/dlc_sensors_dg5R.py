#/usr/bin/python
# -*- coding:utf-8 -*-
import sys
sys.path.append('/home/gadgetini/High-Precision-AD-DA-Board-Code/RaspberryPI/ADS1256/python3')
import ADS1256
import math
import numpy as np
import adafruit_dht
import time
import RPi.GPIO as GPIO
import board
import random
import time
import requests
import adafruit_dht
import mpu6050 as gyro
import subprocess
import redis
import numpy as np

ADC = ADS1256.ADS1256()
ADC.ADS1256_init()
dhtDevice = adafruit_dht.DHT11(board.D4)

# ADS1256_GetAll() reads all channels at once.
# Collect N samples once and share across all channel functions to avoid redundant reads.
def _collect_adc_samples(n=30):
    return [ADC.ADS1256_GetAll() for _ in range(n)]

# DHT11 connected to GPIO 4
# Error happen fairly often, DHT's are hard to read, just keep going
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

# Coolant temperature fomula generate by several measured data using linear regression.
# x: Raw sensing data(ADC_Value, y: Degree celcisous)
def get_coolant_temp(ad_index, adc_samples=None):
    VREF = 5.0
    VIN_DIV = 3.3
    R_FIXED = 10000.0
    DEFAULT_C = 0

    SH_A = 0.0010957
    SH_B = 0.0002395
    SH_C = 0.000000073454

    try:
        if adc_samples is None:
            adc_samples = _collect_adc_samples()

        vs = [float(s[ad_index]) * VREF / 0x7fffff for s in adc_samples]
        vout = float(np.median(vs))

        if vout <= 0.001 or vout >= (VIN_DIV - 0.001):
            return DEFAULT_C

        r_ntc = (vout * R_FIXED) / (VIN_DIV - vout)

        ln_r = math.log(r_ntc)
        temp_k = 1.0 / (SH_A + (SH_B * ln_r) + (SH_C * (ln_r**3)))
        celsius = temp_k - 273.15

        return round(celsius, 1)

    except Exception:
        return DEFAULT_C


# is_leak = 1 is coolant leak detected, 0 is stable.
def get_coolant_leak_detection(adc_samples=None):
    if adc_samples is None:
        adc_samples = _collect_adc_samples()
    samples = [round(float(s[7] * 5.0 / 0x7fffff), 3) for s in adc_samples]
    return 1 if float(np.median(samples)) < 3.0 else 0

# is_full = 0 is coolant tank empty, 1 is full
def get_coolant_level_detection(adc_samples=None):
    if adc_samples is None:
        adc_samples = _collect_adc_samples()
    samples = [round(float(s[6] * 5.0 / 0x7fffff), 3) for s in adc_samples]
    return 0 if float(np.median(samples)) > 1.2 else 1

adc = _collect_adc_samples()
print(get_coolant_level_detection(adc))
print(get_coolant_leak_detection(adc))
print(get_coolant_temp(2, adc))
print(get_coolant_temp(3, adc))
print(get_coolant_temp(4, adc))
print(get_coolant_temp(5, adc))
print(get_air_temp())
print(get_air_humit())
