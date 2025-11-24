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
        #7 = leak detection leak = 1
        gauge_metric.add_metric(["dg5W","LEAK detection","if leak: value = 1"], int(client.get("coolant_leak")))
        #6 = water level full = 1
        gauge_metric.add_metric(["dg5W","Coolant level", "if full: value = 1"], int(client.get("coolant_level")))
        #4 = water temp 34.3 = 1.386 35 = 1.360 35.6 = 1.346 37.6 = 1.282 35.7 = 1.348
        gauge_metric.add_metric(["dg5W","Coolant temperature", "degree celcious"], float(client.get("coolant_temp")))
        gauge_metric.add_metric(["dg5W","Air temperature", "degree celcious"], float(client.get("air_temp")))
        gauge_metric.add_metric(["dg5W","Air humidity", "%"], float(client.get("air_humit")))
        gauge_metric.add_metric(["dg5W","Chassis stability", "1 is stable, 0 is unstable, may server in oscillatting"], int(client.get("chassis_stabil")))
        
        for keys in client.keys("gpu_temp_*"):
            number = str(keys).split("_")[2]
            print(number)
            gauge_metric.add_metric(["dg5W","H200NVL_" + str(number) +" asic temperature", "degree celcious"], float(client.get(keys)))

        for keys in client.keys("gpu_curr_pwr_*"):
            number = str(keys).split("_")[3]
            print(number)
            gauge_metric.add_metric(["dg5W","H200NVL_" + str(number) +"current power usage", "W"], float(client.get(keys)))

        for keys in client.keys("gpu_max_pwr_*"):
            number = str(keys).split("_")[3]
            print(number)
            gauge_metric.add_metric(["dg5W","H200NVL_" + str(number) +" Max power limit", "W"], float(client.get(keys)))

        for keys in client.keys("gpu_curr_mem_*"):
            number = str(keys).split("_")[3]
            print(number)
            gauge_metric.add_metric(["dg5W","H200NVL_" + str(number) +" current memory usage", "byte"], float(client.get(keys)))
 
        for keys in client.keys("gpu_max_mem_*"):
            number = str(keys).split("_")[3]
            print(number)
            gauge_metric.add_metric(["dg5W","H200NVL_" + str(number) +" memory capacity", "byte"], float(client.get(keys)))
 
        gauge_metric.add_metric(["dg5W","CPU0 temperature", "degree celcious"], float(client.get("cpu_temp_0")))
        gauge_metric.add_metric(["dg5W","CPU1 temperature", "degree celcious"], float(client.get("cpu_temp_1")))
        gauge_metric.add_metric(["dg5W","CPU Usage", "%"], float(client.get("cpu_usage")))
        gauge_metric.add_metric(["dg5W","Memory_total","GB"], float(client.get("mem_total")))
        gauge_metric.add_metric(["dg5W","Memory_usage","GB"], float(client.get("mem_usage")))
        gauge_metric.add_metric(["dg5W","Memory_available","GB"], float(client.get("mem_available")))

        yield gauge_metric

if __name__ == "__main__":
    client = redis.StrictRedis(host='localhost', port=6379, db=0)
    port = 9003
    frequency = 2
    try:
        registry = CollectorRegistry()
        sensor_collector = DLC_sensor_Collector()
        registry.register(sensor_collector)
        start_http_server(port, registry=registry)
    except Exception as e:
        # If sensing fail, initialize ADS1256 module.
        pass
    while True:
        #print("DLC sensor telemetry initiate..")
        time.sleep(frequency)







