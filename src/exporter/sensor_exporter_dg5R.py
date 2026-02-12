#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
sys.path.append('/home/gadgetini/High-Precision-AD-DA-Board-Code/RaspberryPI/ADS1256/python3')
import time
from prometheus_client import start_http_server, CollectorRegistry
from prometheus_client.core import GaugeMetricFamily
import redis

client = redis.StrictRedis(host='localhost', port=6379, db=0)

def _get_int(key, default=0):
    v = client.get(key)
    if v is None:
        return int(default)
    try:
        return int(v)
    except Exception:
        try:
            return int(float(v))
        except Exception:
            return int(default)

def _get_float(key, default=0.0):
    v = client.get(key)
    if v is None:
        return float(default)
    try:
        return float(v)
    except Exception:
        try:
            return float(v.decode("utf-8"))
        except Exception:
            return float(default)

class DLC_sensor_Collector(object):

    def collect(self):
        gauge_metric = GaugeMetricFamily(
            "DLC_sensors_gauge",
            "deepgadget DLC sensors telemetry",
            labels=['server_name','metric','description']
        )

        # Leak detection: leak = 1
        gauge_metric.add_metric(
            ["dg5R", "LEAK detection", "if leak: value = 1"],
            _get_int("coolant_leak")
        )

        # Coolant level: full = 1
        gauge_metric.add_metric(
            ["dg5R", "Coolant level", "if full: value = 1"],
            _get_int("coolant_level")
        )

        # Coolant temperatures (Renamed from AD2~AD5 to inlet/outlet) + deltaT
        # Blue = inlet, Red = outlet
        gauge_metric.add_metric(
            ["dg5R", "Coolant temperature inlet1", "degree celcious"],
            _get_float("coolant_temp_inlet1")
        )
        gauge_metric.add_metric(
            ["dg5R", "Coolant temperature outlet1", "degree celcious"],
            _get_float("coolant_temp_outlet1")
        )
        gauge_metric.add_metric(
            ["dg5R", "Coolant deltaT1", "degree celcious"],
            _get_float("coolant_delta_t1")
        )

        gauge_metric.add_metric(
            ["dg5R", "Coolant temperature inlet2", "degree celcious"],
            _get_float("coolant_temp_inlet2")
        )
        gauge_metric.add_metric(
            ["dg5R", "Coolant temperature outlet2", "degree celcious"],
            _get_float("coolant_temp_outlet2")
        )
        gauge_metric.add_metric(
            ["dg5R", "Coolant deltaT2", "degree celcious"],
            _get_float("coolant_delta_t2")
        )

        # Air sensors
        gauge_metric.add_metric(
            ["dg5R", "Air temperature", "degree celcious"],
            _get_float("air_temp")
        )
        gauge_metric.add_metric(
            ["dg5R", "Air humidity", "%"],
            _get_float("air_humit")
        )

        # NOTE: GPU metrics blocks are kept as-is (commented out)
        for keys in client.keys("gpu_temp_*"):
            number = str(keys).split("_")[2]
            print(number)
            # gauge_metric.add_metric(["dg5R","H200NVL_" + str(number) +" asic temperature", "degree celcious"], _get_float(keys))

        for keys in client.keys("gpu_curr_pwr_*"):
            number = str(keys).split("_")[3]
            print(number)
            # gauge_metric.add_metric(["dg5R","H200NVL_" + str(number) +" current power usage", "W"], _get_float(keys))

        for keys in client.keys("gpu_max_pwr_*"):
            number = str(keys).split("_")[3]
            print(number)
            # gauge_metric.add_metric(["dg5R","H200NVL_" + str(number) +" Max power limit", "W"], _get_float(keys))

        for keys in client.keys("gpu_curr_mem_*"):
            number = str(keys).split("_")[3]
            print(number)
            # gauge_metric.add_metric(["dg5R","H200NVL_" + str(number) +" current memory usage", "byte"], _get_float(keys))

        for keys in client.keys("gpu_max_mem_*"):
            number = str(keys).split("_")[3]
            print(number)
            # gauge_metric.add_metric(["dg5R","H200NVL_" + str(number) +" memory capacity", "byte"], _get_float(keys))

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
    except Exception:
        # If exporter init fails, just keep process alive (systemd watchdog 등에서 재기동 가능)
        pass

    while True:
        time.sleep(frequency)

