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
gyroDevice = gyro.mpu6050(0x68)
boot_stabil = gyroDevice.get_gyro_data()

# DHT11 connected to GPIO 4
def get_air_temp():
    curr_temp = 26.5
    try:
        bias = random.random()
        bias_trim = round(bias, 1)
        curr_temp = dhtDevice.temperature + bias_trim
    except Exception as e:
        print("dht sensing error")
        # Error happen fairly often, DHT's are hard to read, just keep going 
        pass
    finally:
        return curr_temp
        
def get_air_humit():
    curr_humit = 25.2
    try:
        bias = random.random()
        bias_trim = round(bias, 1)
        curr_humit = dhtDevice.humidity + bias_trim
    except Exception as e:
        print(e)
        print("dht sensing error")
        # Error happen fairly often, DHT's are hard to read, just keep going 
        pass
    finally:
        return curr_humit
        
# Coolant temperature fomula generate by several measured data using linear regression. 
# x: Raw sensing data(ADC_Value, y: Degree celcisous)
def get_coolant_temp():
    VIN_DIV = 3.3     # Based on 3.3V circuit in Image 2
    R_FIXED = 10000.0 
    DEFAULT_C = 0

    # Precise Coefficients derived from Image 2 R-T Table
    SH_A = 0.0010957
    SH_B = 0.0002395
    SH_C = 0.000000073454

    try:
        vs = []
        for _ in range(7):
            ADC_Value = ADC.ADS1256_GetAll()
            raw = float(ADC_Value[4]) 
            vout = raw * VREF / 0x7fffff
            vs.append(vout)

        vout = float(np.median(vs))

        if vout <= 0.001 or vout >= (VIN_DIV - 0.001):
            return DEFAULT_C

        # Calculate R_ntc using the 3.3V divider source
        r_ntc = (vout * R_FIXED) / (VIN_DIV - vout)

        # Steinhart-Hart Equation
        ln_r = math.log(r_ntc)
        # 1/T = A + B*ln(R) + C*(ln(R)^3)
        inv_t = SH_A + (SH_B * ln_r) + (SH_C * (ln_r ** 3))
        temp_k = 1.0 / inv_t
        celsius = temp_k - 273.15

        return round(celsius, 1)

    except Exception:
        return DEFAULT_C

# is_stable 1 is stable, 0 is unstable.
def get_chassis_stabil():
    # get x, y, z, axis value. type: dict
    current_stabil = gyroDevice.get_gyro_data()
    curr_x = current_stabil['x'] 
    curr_y = current_stabil['y']
    curr_z = current_stabil['z']
    init_x = boot_stabil['x']
    init_y = boot_stabil['y']
    init_z = boot_stabil['z']
    is_stable = 1
    # Compare current xyz coordinate data with boot xyz data. 
    if abs(curr_x - init_x) > 5 and abs(curr_y - init_y) > 5 or abs(curr_z - init_z) > 5:
        is_stable = 0
    else:
        is_stable = 1
    return is_stable

# is_leak = 1 is coolant leak detected, 0 is stable.
def get_coolant_leak_detection():
    is_leak = 0
    ADC_Value = ADC.ADS1256_GetAll()
    raw_data = round(float(ADC_Value[7]*5.0/0x7fffff),3)
    if raw_data < 3.0:
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
