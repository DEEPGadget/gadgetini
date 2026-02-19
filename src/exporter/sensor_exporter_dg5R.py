#!/usr/bin/python3
# -*- coding: utf-8 -*-
import time
from prometheus_client import start_http_server, CollectorRegistry
from prometheus_client.core import GaugeMetricFamily
import redis

client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

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
        srv = "dg5R"

        # ── Leak & Level ───────────────────────────────────────────
        g.add_metric([srv, "cooling", "leak_detected",      "bool", ""],     get_int("coolant_leak"))
        g.add_metric([srv, "cooling", "level_full",         "bool", ""],     get_int("coolant_level"))

        # ── Coolant temperatures & ΔT ──────────────────────────────
        for ch in ["1", "2"]:
            g.add_metric([srv, "cooling", f"inlet{ch}_temp",   "°C",  ""], get_float(f"coolant_temp_inlet{ch}"))
            g.add_metric([srv, "cooling", f"outlet{ch}_temp",  "°C",  ""], get_float(f"coolant_temp_outlet{ch}"))
            g.add_metric([srv, "cooling", f"delta_t{ch}",      "°C",  ""], get_float(f"coolant_delta_t{ch}"))

        # ── Air (internal) ─────────────────────────────────────────
        g.add_metric([srv, "environment", "air_temp",        "°C",   ""], get_float("air_temp"))
        g.add_metric([srv, "environment", "air_humidity",    "%RH",  ""], get_float("air_humit"))

        # ── GPUs (0~7) ─────────────────────────────────────────────
        for i in range(8):
            name_bytes = client.get(f"gpu_name_{i}")
            gpu_name = name_bytes.strip() if name_bytes else f"GPU{i}"
            extra = gpu_name.replace(" ", "_").replace("/", "-")

            temp  = get_float(f"gpu_temp_{i}")
            pwr   = get_float(f"gpu_curr_pwr_{i}")
            pwr_l = get_float(f"gpu_max_pwr_{i}")
            mem_u = get_float(f"gpu_curr_mem_{i}")
            mem_t = get_float(f"gpu_max_mem_{i}")
            mem_util = (mem_u / mem_t * 100) if mem_t > 10 else 0.0

            g.add_metric([srv, f"gpu{i}", "temperature",      "°C",   extra], temp)
            g.add_metric([srv, f"gpu{i}", "power_current",    "W",    extra], pwr)
            g.add_metric([srv, f"gpu{i}", "power_limit",      "W",    extra], pwr_l)
            g.add_metric([srv, f"gpu{i}", "memory_used",      "MiB",  extra], mem_u)
            g.add_metric([srv, f"gpu{i}", "memory_total",     "MiB",  extra], mem_t)
            g.add_metric([srv, f"gpu{i}", "memory_util",      "%",    extra], round(mem_util, 1))

        # ── CPUs ───────────────────────────────────────────────────
        g.add_metric([srv, "cpu", "usage_total", "%", ""], get_float("cpu_usage"))

        for i in [0, 1]:
            g.add_metric([srv, f"cpu{i}", "temperature", "°C",  ""], get_float(f"cpu_temp_{i}"))
            g.add_metric([srv, f"cpu{i}", "power",       "W",   ""], get_float(f"cpu_curr_pwr_{i}"))

        # ── System Memory ──────────────────────────────────────────
        g.add_metric([srv, "memory", "total",     "GiB", ""], get_float("mem_total"))
        g.add_metric([srv, "memory", "available", "GiB", ""], get_float("mem_available"))
        g.add_metric([srv, "memory", "usage",     "%",   ""], get_float("mem_usage"))

        # ── Network Interfaces status ──────────────────────────────
        nic_patterns = [
            "ens102f0", "ens102f1",
            "enP1s125f0np0", "enP1s125f1np1",
            "enxfef11ad36eb7", "enxee7c7c859844"
        ]
        for nic in nic_patterns:
            key = f"nic_{nic}_stat"
            if client.exists(key):
                val = get_int(key)
                g.add_metric([srv, "network", "link_status", "1=up", nic], val)

        # ── Infiniband NIC ─────────────────────────────────────────
        if client.exists("ib_nic_temp"):
            g.add_metric([srv, "ib", "temperature", "°C", ""], get_float("ib_nic_temp"))

        # ── Host / Server alive ────────────────────────────────────
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
