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

# DHT11 connected to GPIO 4
def get_air_temp():
    curr_temp = 0
    try:
        curr_temp = dhtDevice.temperature 
    except Exception as e:
        print("dht sensing error")
        # Error happen fairly often, DHT's are hard to read, just keep going 
        pass
    finally:
        return curr_temp
        
def get_air_humit():
    curr_humit = 0
    try:
        curr_humit = dhtDevice.humidity 
    except Exception as e:
        print(e)
        print("dht sensing error")
        # Error happen fairly often, DHT's are hard to read, just keep going 
        pass
    finally:
        return curr_humit
        
# Coolant temperature fomula generate by several measured data using linear regression. 
# x: Raw sensing data(ADC_Value, y: Degree celcisous)
def get_coolant_temp(ad_index):
    VREF = 5.0
    VIN_DIV = 3.3
    R_FIXED = 10000.0
    DEFAULT_C = 0

    SH_A = 0.0010957
    SH_B = 0.0002395
    SH_C = 0.000000073454

    try:
        vs = []
        for _ in range(7):
            ADC_Value = ADC.ADS1256_GetAll()
            raw = float(ADC_Value[ad_index])
            vs.append(raw * VREF / 0x7fffff)

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
def get_coolant_leak_detection():
    is_leak = 0
    count = 0 
    for i in range(10):
        ADC_Value = ADC.ADS1256_GetAll()
        raw_data = round(float(ADC_Value[7]*5.0/0x7fffff),3)
        if raw_data < 3.0:
            count += 1
    if count > 8:
        is_leak = 1
    return is_leak

# is_full = 0 is coolant tank empty, 1 is full
def get_coolant_level_detection():
    ADC_Value = ADC.ADS1256_GetAll()
    is_full = 1 
    curr_level = round(float(ADC_Value[6]*5.0/0x7fffff),3)
    if curr_level > 1.2:
        is_full = 0
    return is_full

print(get_coolant_level_detection())
print(get_coolant_leak_detection())
print(get_coolant_temp(2))
print(get_coolant_temp(3))
print(get_coolant_temp(4))
print(get_coolant_temp(5))
print(get_air_temp())
print(get_air_humit())
