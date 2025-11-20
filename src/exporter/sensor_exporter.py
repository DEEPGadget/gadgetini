#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
sys.path.append('/home/gadgetini/High-Precision-AD-DA-Board-Code/RaspberryPI/ADS1256/python3')
import time
from prometheus_client import start_http_server, CollectorRegistry
from prometheus_client.core import GaugeMetricFamily
import redis

SERVER_NAME = "dg5W"
client = redis.StrictRedis(host='localhost', port=6379, db=0)

def get_redis_or_default(key, default=0.0):
    value = client.get(key)
    if value is None:
        return default
    try:
        decoded = value.decode('utf-8').strip()
        if decoded == '':
            return default
        return float(decoded)
    except:
        return default

def discover_gpu_indices():
    indices = set()
    patterns = ["9070XT_asic_temp_*", "9070XT_pwr_*", "9070XT_mem_temp_*"]
    for pattern in patterns:
        for key in client.keys(pattern):
            try:
                key_str = key.decode("utf-8")
                parts = key_str.rsplit("_", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    indices.add(int(parts[1]))
            except:
                continue
    return sorted(indices) or [0]

class DLC_sensor_Collector(object):
    def collect(self):
        gauge_metric = GaugeMetricFamily(
            "DLC_sensors_gauge",
            "deepgadget DLC sensors telemetry",
            labels=['server_name', 'metric', 'description']
        )

        gauge_metric.add_metric([SERVER_NAME, "LEAK detection", "if leak: value = 1"], get_redis_or_default("coolant_leak"))
        gauge_metric.add_metric([SERVER_NAME, "Coolant level", "if full: value = 1"], get_redis_or_default("coolant_level"))
        gauge_metric.add_metric([SERVER_NAME, "Coolant temperature", "degree celcious"], get_redis_or_default("coolant_temp"))
        gauge_metric.add_metric([SERVER_NAME, "Air temperature", "degree celcious"], get_redis_or_default("air_temp"))
        gauge_metric.add_metric([SERVER_NAME, "Air humidity", "%"], get_redis_or_default("air_humit"))
        gauge_metric.add_metric([SERVER_NAME, "Chassis stability", "1 is stable, 0 is unstable, may server in oscillatting"], get_redis_or_default("chassis_stabil"))

        gpu_indices = discover_gpu_indices()

        for idx in gpu_indices:
            gauge_metric.add_metric([SERVER_NAME, f"RX9070XT_{idx} asic temperature", "degree celcious"], get_redis_or_default(f"9070XT_asic_temp_{idx}"))
            gauge_metric.add_metric([SERVER_NAME, f"RX9070XT_{idx} power usage", "W"], get_redis_or_default(f"9070XT_pwr_{idx}"))
            gauge_metric.add_metric([SERVER_NAME, f"RX9070XT_{idx} memory temperature", "degree celcious"], get_redis_or_default(f"9070XT_mem_temp_{idx}"))

        gauge_metric.add_metric([SERVER_NAME, "CPU temperature", "degree celcious"], get_redis_or_default("cpu_temp_0"))
        gauge_metric.add_metric([SERVER_NAME, "CPU Usage", "%"], get_redis_or_default("cpu_usage"))
        gauge_metric.add_metric([SERVER_NAME, "Memory_total", "GB"], get_redis_or_default("mem_total"))
        gauge_metric.add_metric([SERVER_NAME, "Memory_usage", "GB"], get_redis_or_default("mem_usage"))
        gauge_metric.add_metric([SERVER_NAME, "Memory_available", "GB"], get_redis_or_default("mem_available"))

        yield gauge_metric

if __name__ == "__main__":
    registry = CollectorRegistry()
    registry.register(DLC_sensor_Collector())
    start_http_server(9003, registry=registry)
    while True:
        time.sleep(1)
