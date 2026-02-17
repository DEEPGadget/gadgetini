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

        # ── GPU metrics (from serial_receiver: gpuN_gpu_*) ──
        for key in client.keys("*_gpu_temp"):
            idx = key.decode().split("_")[0].replace("gpu", "")
            name = client.get(f"gpu{idx}_gpu_name")
            gpu_label = name.decode() + "_" + idx if name else "GPU_" + idx

            gauge_metric.add_metric(
                ["dg5R", gpu_label + " asic temperature", "degree celcious"],
                _get_float(f"gpu{idx}_gpu_temp")
            )
            gauge_metric.add_metric(
                ["dg5R", gpu_label + " current power usage", "W"],
                _get_float(f"gpu{idx}_gpu_power")
            )
            gauge_metric.add_metric(
                ["dg5R", gpu_label + " Max power limit", "W"],
                _get_float(f"gpu{idx}_gpu_power_limit")
            )
            gauge_metric.add_metric(
                ["dg5R", gpu_label + " core utilization", "%"],
                _get_float(f"gpu{idx}_gpu_util")
            )
            gauge_metric.add_metric(
                ["dg5R", gpu_label + " memory utilization", "%"],
                _get_float(f"gpu{idx}_gpu_mem_util")
            )

        # ── CPU metrics (from serial_receiver: cpu_N_temp, cpu_util, cpu_power_N) ──
        for key in client.keys("cpu_*_temp"):
            idx = key.decode().split("_")[1]
            gauge_metric.add_metric(
                ["dg5R", "CPU" + idx + " temperature", "degree celcious"],
                _get_float(key)
            )

        for key in client.keys("cpu_power_*"):
            idx = key.decode().split("_")[2]
            gauge_metric.add_metric(
                ["dg5R", "CPU" + idx + " power usage", "W"],
                _get_float(key)
            )

        gauge_metric.add_metric(
            ["dg5R", "CPU Usage", "%"],
            _get_float("cpu_util")
        )

        # ── Memory metrics (from serial_receiver: total_mem, avail_mem, etc.) ──
        gauge_metric.add_metric(
            ["dg5R", "Memory_total", "GB"],
            _get_float("total_mem")
        )
        gauge_metric.add_metric(
            ["dg5R", "Memory_usage", "GB"],
            _get_float("used_mem")
        )
        gauge_metric.add_metric(
            ["dg5R", "Memory_available", "GB"],
            _get_float("avail_mem")
        )
        gauge_metric.add_metric(
            ["dg5R", "Swap_usage", "GB"],
            _get_float("used_swp")
        )
        gauge_metric.add_metric(
            ["dg5R", "OOM_count", "count"],
            _get_int("oom_count")
        )

        # ── Network metrics (from serial_receiver: net_*) ──
        gauge_metric.add_metric(
            ["dg5R", "Network link status", "1=UP 0=DOWN"],
            _get_int("net_link_status")
        )
        gauge_metric.add_metric(
            ["dg5R", "Network TX throughput", "Gbps"],
            _get_float("net_tx_bps")
        )
        gauge_metric.add_metric(
            ["dg5R", "Network RX throughput", "Gbps"],
            _get_float("net_rx_bps")
        )
        gauge_metric.add_metric(
            ["dg5R", "Network errors rate", "%"],
            _get_float("net_errors_rate")
        )
        gauge_metric.add_metric(
            ["dg5R", "Network drops rate", "%"],
            _get_float("net_drops_rate")
        )

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

