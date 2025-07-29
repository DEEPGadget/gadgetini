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
        curr_temp = dhtDevice.humidity + bias_trim
    except Exception as e:
        print("dht sensing error")
        # Error happen fairly often, DHT's are hard to read, just keep going 
        pass
    finally:
        return curr_humit
        
# Coolant temperature fomula generate by several measured data using linear regression. 
# x: Raw sensing data(ADC_Value, y: Degree celcisous)
'''
def get_coolant_temp():
    ADC_Value = ADC.ADS1256_GetAll()
    coeff_a = 50.453
    coeff_b = -1.177
    raw = 0
    celcious = 0
    if float(ADC_Value[4]*5.0/0x7fffff) < 1:
        raw = 1.282
        celcious = coeff_a * raw ** coeff_b
    else:
        celcious = coeff_a * float(ADC_Value[4]*5.0/0x7fffff) ** coeff_b
    celcious = round(celcious, 1)
    return celcious
'''

def get_coolant_temp():
    sample_buf = []
    raw_val = 0
    for i in range(5):
        ADC_Value = ADC.ADS1256_GetAll()
        sample_buf.append( float(ADC_Value[4]*5.0/0x7fffff))
    np.abs(sample_buf)
    sample_buf.sort()
    if sample_buf[0] - sample_buf[-1] > 2.5:
        raw_val = sample_buf[-1]
    else:
        raw_val = sample_buf[0]
    coeff_a = 50.393
    coeff_b = -1.177
    raw = 0
    celcious = 0
    
    celcious = coeff_a * raw_val ** coeff_b
    celcious = round(celcious, 1)
    return celcious


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
    is_full = 0 
    curr_level = round(float(ADC_Value[6]*5.0/0x7fffff),3)
    if curr_level > 2.2:
        is_full = 1
    return is_full



# test 
'''
while True:
    print(get_coolant_temp_sampling())
    print(get_chassis_stabil())
    print(get_coolant_leak_detection())
    print(get_coolant_level_detection())
    print(get_air_temp())
    print(get_air_humit())
'''
