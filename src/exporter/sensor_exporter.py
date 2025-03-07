#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
sys.path.append('/home/gadgetini/High-Precision-AD-DA-Board-Code/RaspberryPI/ADS1256/python3')
import math
import numpy as np
import time
from prometheus_client import start_http_server, CollectorRegistry
from prometheus_client.core import GaugeMetricFamily
import random
import time
import requests
import subprocess
import redis
client = redis.StrictRedis(host='localhost', port=6379, db=0)

class DLC_sensor_Collector(object):

    def collect(self):
        gauge_metric = GaugeMetricFamily("DLC_sensors_gauge", "deepgadget DLC sensors telemetry", labels=['server_name','metric','description'])
        #7 = leak detection leak = < 4.2
        print(int(client.get("coolant_level")))
        gauge_metric.add_metric(["dg-n300-4","LEAK detection","if leak: value < 4.1"], int(client.get("coolant_leak")))
        #6 = water level LOW > 1
        gauge_metric.add_metric(["dg-n300-4","Coolant level", "if empty: value > 1"], int(client.get("coolant_level")))
        #4 = water temp 34.3 = 1.386 35 = 1.360 35.6 = 1.346 37.6 = 1.282 35.7 = 1.348
        gauge_metric.add_metric(["dg-n300-4","Coolant temperature", "degree celcious"], float(client.get("coolant_temp")))
        gauge_metric.add_metric(["dg-n300-4","Air temperature", "degree celcious"], float(client.get("air_temp")))
        gauge_metric.add_metric(["dg-n300-4","Air humidity", "%"], float(client.get("air_humit")))
        gauge_metric.add_metric(["dg-n300-4","Chassis stability", "1 is stable, 0 is unstable, may server in oscillatting"], int(client.get("chassis_stabil")))
        yield gauge_metric

if __name__ == "__main__":
    port = 9003
    frequency = 2
    try:
        registry = CollectorRegistry()
        sensor_collector = DLC_sensor_Collector()
        registry.register(sensor_collector)
        start_http_server(port, registry=registry)
    except Exception as e:
        # Error happen fairly often, DHT's are hard to read, just keep going
        GPIO.cleanup()
        ADC = ADS1256.ADS1256()
        ADC.ADS1256_init()
        # DHT11 connected to GPIO 4
        dhtDevice = adafruit_dht.DHT11(board.D4)
        gyroDevice = gyro.mpu6050(0x68)
        # If sensing fail, initialize ADS1256 module.
        pass
    while True:
        #print("DLC sensor telemetry initiate..")
        time.sleep(frequency)
