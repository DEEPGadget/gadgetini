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
    """
    Assumption (your request): ADS1256 VREF=5.0V, but thermistor divider VIN=3.3V.

    Divider wiring (same as 그림1):
      VIN_DIV(3.3V) --- R_FIXED(10k) --- Vout(AD4) --- NTC(10k) --- GND

    We must:
      1) Convert RAW -> Vout using ADC reference (VREF)
      2) Convert Vout -> Rntc using divider supply (VIN_DIV)
      3) Convert Rntc -> Celsius using Beta (or S-H)
    """
    import math
    import numpy as np

    # --- voltages (separated!) ---
    VREF = 5.0        # ADC reference used for RAW->V conversion (ASSUMED)
    VIN_DIV = 3.3     # actual divider supply measured at 3.3V pin (CONFIRMED by you)

    # --- divider / thermistor parameters ---
    R_FIXED = 10_000.0
    R25 = 10_000.0
    BETA = 3950.0     # TODO: replace with Barrow NTC B-value if known
    T0_K = 25.0 + 273.15

    DEFAULT_C = 32.4

    try:
        # 1) read several samples
        vs = []
        for _ in range(7):
            ADC_Value = ADC.ADS1256_GetAll()
            raw = float(ADC_Value[4])

            # RAW -> Vout using ADC's VREF (ASSUMED 5V)
            vout = raw * VREF / 0x7fffff
            vs.append(vout)

        # 2) robust filtering: median
        vout = float(np.median(vs))

        # 3) clamp to physical range of divider (0..VIN_DIV)
        # because divider is powered by 3.3V even if VREF is 5V
        if vout <= 0.0:
            return DEFAULT_C
        if vout >= VIN_DIV:
            # if you see this often, RAW->Vout scaling or channel wiring is likely wrong
            return DEFAULT_C

        # 4) Vout -> Rntc (divider math uses VIN_DIV)
        r_ntc = R_FIXED * vout / (VIN_DIV - vout)
        if r_ntc <= 0:
            return DEFAULT_C

        # 5) Rntc -> Celsius (Beta)
        ln = math.log(r_ntc / R25)
        temp_k = 1.0 / ((ln / BETA) + (1.0 / T0_K))
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
