#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Redis Keys written by data_crawler.py / data_crawler_host.py
# Writer column: gadgetini = data_crawler.py, host = data_crawler_host.py
#
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ MACHINE: dg5r                                                               │
# ├─────────────────────────┬────────────┬────────┬───────────────────────────┤
# │ Key                     │ Unit       │ Writer │ Description                │
# ├─────────────────────────┼────────────┼────────┼───────────────────────────┤
# │ coolant_temp_inlet1     │ °C         │ gadget │ inlet  temp ch1 (ADC2)    │
# │ coolant_temp_inlet2     │ °C         │ gadget │ inlet  temp ch2 (ADC5)    │
# │ coolant_temp_outlet1    │ °C         │ gadget │ outlet temp ch1 (ADC3)    │
# │ coolant_temp_outlet2    │ °C         │ gadget │ outlet temp ch2 (ADC4)    │
# │ coolant_delta_t1        │ °C         │ gadget │ ΔT = outlet1 - inlet1     │
# │ coolant_delta_t2        │ °C         │ gadget │ ΔT = outlet2 - inlet2     │
# │ coolant_leak            │ 0/1 bool   │ gadget │ leak detected (1=Leak)    │
# │ coolant_level           │ 0/1 bool   │ gadget │ coolant level (1=OK)      │
# │ air_temp                │ °C         │ gadget │ internal air temp (DHT11) │
# │ air_humit               │ %RH        │ gadget │ internal air humidity     │
# │ gpu_name_{0~7}          │ string     │ host   │ GPU model name            │
# │ gpu_temp_{0~7}          │ °C         │ host   │ GPU temperature           │
# │ gpu_curr_pwr_{0~7}      │ W          │ host   │ GPU current power         │
# │ gpu_max_pwr_{0~7}       │ W          │ host   │ GPU power limit           │
# │ gpu_curr_mem_{0~7}      │ MiB        │ host   │ GPU VRAM used             │
# │ gpu_max_mem_{0~7}       │ MiB        │ host   │ GPU VRAM total            │
# │ cpu_usage               │ %          │ host   │ total CPU usage           │
# │ cpu_temp_{0~1}          │ °C         │ host   │ CPU package temp/socket   │
# │ cpu_curr_pwr_{0~1}      │ W          │ host   │ CPU power/socket (IPMI)   │
# │ mem_total               │ GiB        │ host   │ total system memory       │
# │ mem_usage               │ GiB        │ host   │ memory in use             │
# │ mem_available           │ GiB        │ host   │ memory available          │
# │ nic_{ifname}_stat       │ 0/1 bool   │ host   │ NIC link (1=UP)           │
# │ ib_nic_temp             │ °C         │ host   │ IB NIC ASIC temp (opt.)   │
# │ host_stat               │ 0/1 bool   │ gadget │ host online (1=online)    │
# │ host_ttl                │ ms epoch   │ host   │ TTL key; expires in 5s    │
# └─────────────────────────┴────────────┴────────┴───────────────────────────┘
#
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ MACHINE: dg5w                                                               │
# ├─────────────────────────┬────────────┬────────┬───────────────────────────┤
# │ Key                     │ Unit       │ Writer │ Description                │
# ├─────────────────────────┼────────────┼────────┼───────────────────────────┤
# │ coolant_temp_inlet1     │ °C         │ gadget │ inlet temp ch1 (ADC4)     │
# │ coolant_leak            │ 0/1 bool   │ gadget │ leak detected (1=Leak)    │
# │ coolant_level           │ 0/1 bool   │ gadget │ coolant level (1=OK)      │
# │ air_temp                │ °C         │ gadget │ internal air temp (DHT11) │
# │ air_humit               │ %RH        │ gadget │ internal air humidity     │
# │ chassis_stabil          │ 0/1 bool   │ gadget │ chassis stable (MPU6050)  │
# │ gpu_name_{0~7}          │ string     │ host   │ GPU model name            │
# │ gpu_temp_{0~7}          │ °C         │ host   │ GPU temperature           │
# │ gpu_curr_pwr_{0~7}      │ W          │ host   │ GPU current power         │
# │ gpu_max_pwr_{0~7}       │ W          │ host   │ GPU power limit           │
# │ gpu_curr_mem_{0~7}      │ MiB        │ host   │ GPU VRAM used             │
# │ gpu_max_mem_{0~7}       │ MiB        │ host   │ GPU VRAM total            │
# │ cpu_usage               │ %          │ host   │ total CPU usage           │
# │ cpu_temp_{0~1}          │ °C         │ host   │ CPU package temp/socket   │
# │ cpu_curr_pwr_{0~1}      │ W          │ host   │ CPU power/socket (IPMI)   │
# │ mem_total               │ GiB        │ host   │ total system memory       │
# │ mem_usage               │ GiB        │ host   │ memory in use             │
# │ mem_available           │ GiB        │ host   │ memory available          │
# │ nic_{ifname}_stat       │ 0/1 bool   │ host   │ NIC link (1=UP)           │
# │ ib_nic_temp             │ °C         │ host   │ IB NIC ASIC temp (opt.)   │
# │ host_stat               │ 0/1 bool   │ gadget │ host online (1=online)    │
# │ host_ttl                │ ms epoch   │ host   │ TTL key; expires in 5s    │
# └─────────────────────────┴────────────┴────────┴───────────────────────────┘

import time
from prometheus_client import start_http_server, CollectorRegistry
from prometheus_client.core import GaugeMetricFamily
import redis
from machine_config import MACHINE, COOLANT_CHANNELS

client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

CHANNELS = COOLANT_CHANNELS.get(MACHINE, {})


def get_float(key, default=0.0):
    try:
        v = client.get(key)
        return float(v) if v is not None else default
    except:
        return default


def get_int(key, default=0):
    try:
        v = client.get(key)
        return int(v) if v is not None else default
    except:
        return default


class DLCCollector:
    def collect(self):
        g = GaugeMetricFamily(
            "dlc_system_sensor",
            "DeepGadget DLC server sensors & telemetry",
            labels=["server", "component", "metric", "unit", "extra"]
        )
        srv = MACHINE

        # Cooling - leak & level
        g.add_metric([srv, "cooling", "leak_detected", "bool", ""], get_int("coolant_leak"))
        g.add_metric([srv, "cooling", "level_full",    "bool", ""], get_int("coolant_level"))

        # Cooling temperatures (channels from config)
        for name in CHANNELS:
            g.add_metric([srv, "cooling", f"{name}_temp", "°C", ""], get_float(f"coolant_temp_{name}"))

        # expose delta_t only when inlet+outlet pair exists (dg5w has inlet1 only for now, skip)
        if 'inlet1' in CHANNELS and 'outlet1' in CHANNELS:
            g.add_metric([srv, "cooling", "delta_t1", "°C", ""], get_float("coolant_delta_t1"))
        if 'inlet2' in CHANNELS and 'outlet2' in CHANNELS:
            g.add_metric([srv, "cooling", "delta_t2", "°C", ""], get_float("coolant_delta_t2"))

        # Chassis stability (dg5w only)
        if MACHINE == 'dg5w':
            g.add_metric([srv, "chassis", "stability", "bool", ""], get_int("chassis_stabil"))

        # Environment
        g.add_metric([srv, "environment", "air_temp",     "°C",  ""], get_float("air_temp"))
        g.add_metric([srv, "environment", "air_humidity", "%RH", ""], get_float("air_humit"))

        # GPUs (0~7)
        for i in range(8):
            gpu_name = (client.get(f"gpu_name_{i}") or f"GPU{i}").strip()
            extra = (gpu_name.replace(" ", "_").replace("/", "-")
                             .replace(",", "").replace("(", "").replace(")", ""))
            mem_used  = get_float(f"gpu_curr_mem_{i}")
            mem_total = get_float(f"gpu_max_mem_{i}")
            mem_pct   = (mem_used / mem_total * 100) if mem_total > 0 else 0.0
            g.add_metric([srv, f"gpu{i}", "temperature",      "°C",  extra], get_float(f"gpu_temp_{i}"))
            g.add_metric([srv, f"gpu{i}", "power_current",    "W",   extra], get_float(f"gpu_curr_pwr_{i}"))
            g.add_metric([srv, f"gpu{i}", "power_limit",      "W",   extra], get_float(f"gpu_max_pwr_{i}"))
            g.add_metric([srv, f"gpu{i}", "memory_used",      "MiB", extra], mem_used)
            g.add_metric([srv, f"gpu{i}", "memory_total",     "MiB", extra], mem_total)
            g.add_metric([srv, f"gpu{i}", "memory_available", "%",   extra], mem_pct)

        # CPU
        g.add_metric([srv, "cpu", "usage_total", "%", ""], get_float("cpu_usage"))
        for i in [0, 1]:
            g.add_metric([srv, f"cpu{i}", "temperature", "°C", ""], get_float(f"cpu_temp_{i}"))
            g.add_metric([srv, f"cpu{i}", "power",       "W",  ""], get_float(f"cpu_curr_pwr_{i}"))

        # Memory
        g.add_metric([srv, "memory", "total",     "GiB", ""], get_float("mem_total"))
        g.add_metric([srv, "memory", "available", "GiB", ""], get_float("mem_available"))
        g.add_metric([srv, "memory", "usage",     "GiB", ""], get_float("mem_usage"))

        # Network
        seen_nics = set()
        for key in client.keys("nic_*_stat"):
            if not key.startswith("nic_") or not key.endswith("_stat"):
                continue
            nic = key[4:-5]
            if nic in seen_nics:
                continue
            seen_nics.add(nic)
            g.add_metric([srv, "network", "link_status", "1=up", nic], get_int(key))

        # IB
        if client.exists("ib_nic_temp"):
            g.add_metric([srv, "ib", "temperature", "°C", ""], get_float("ib_nic_temp"))

        # Host
        g.add_metric([srv, "system", "host_online", "1=yes", ""], get_int("host_stat"))

        yield g


if __name__ == "__main__":
    registry = CollectorRegistry()
    registry.register(DLCCollector())
    port = 9003
    start_http_server(port, registry=registry)
    print(f"DLC sensor exporter listening on :{port}")
    while True:
        time.sleep(2.5)
