#!/usr/bin/python3
# -*- coding: utf-8 -*-
import time
from prometheus_client import start_http_server, CollectorRegistry
from prometheus_client.core import GaugeMetricFamily
import redis

client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

# Redis KEYS *  (grouped + expected unit)
""" 
[GPU - name]
- gpu_name_0                (string)   GPU model
- gpu_name_1                (string)
- gpu_name_2                (string)
- gpu_name_3                (string)
- gpu_name_4                (string)
- gpu_name_5                (string)
- gpu_name_6                (string)
- gpu_name_7                (string)

[GPU - temp]
- gpu_temp_0                (°C)       GPU temp
- gpu_temp_1                (°C)
- gpu_temp_2                (°C)
- gpu_temp_3                (°C)
- gpu_temp_4                (°C)
- gpu_temp_5                (°C)
- gpu_temp_6                (°C)
- gpu_temp_7                (°C)

[GPU - current power]
- gpu_curr_pwr_0            (W)        GPU current power consumption
- gpu_curr_pwr_1            (W)
- gpu_curr_pwr_2            (W)
- gpu_curr_pwr_3            (W)
- gpu_curr_pwr_4            (W)
- gpu_curr_pwr_5            (W)
- gpu_curr_pwr_6            (W)
- gpu_curr_pwr_7            (W)

[GPU - max power]
- gpu_max_pwr_0             (W)        GPU power limit
- gpu_max_pwr_1             (W)
- gpu_max_pwr_2             (W)
- gpu_max_pwr_3             (W)
- gpu_max_pwr_4             (W)
- gpu_max_pwr_5             (W)
- gpu_max_pwr_6             (W)
- gpu_max_pwr_7             (W)

[GPU - current mem]
- gpu_curr_mem_0            (MiB)      GPU vram currently used 
- gpu_curr_mem_1            (MiB)
- gpu_curr_mem_2            (MiB)
- gpu_curr_mem_3            (MiB)
- gpu_curr_mem_4            (MiB)
- gpu_curr_mem_5            (MiB)
- gpu_curr_mem_6            (MiB)
- gpu_curr_mem_7            (MiB)

[GPU - max mem]
- gpu_max_mem_0             (MiB)      GPU vram total size
- gpu_max_mem_1             (MiB)
- gpu_max_mem_2             (MiB)
- gpu_max_mem_3             (MiB)
- gpu_max_mem_4             (MiB)
- gpu_max_mem_5             (MiB)
- gpu_max_mem_6             (MiB)
- gpu_max_mem_7             (MiB)

[CPU]
- cpu_usage                 (%)        CPU usage
- cpu_temp_0                (°C)       CPU package temperature (socket0)
- cpu_temp_1                (°C)       CPU package temperature (socket1)
- cpu_curr_pwr_0                (W)        CPU0 power consumption (package/socket power)
- cpu_curr_pwr_1                (W)        CPU1 power consumption

[Memory]
- mem_total                 (GiB)    total memory 
- mem_available             (GiB)    available memory
- mem_usage                 (GiB)    memory usage


[NIC]
- nic_ens102f0_stat         (string/boolean(true/false))  link status (UP/DOWN)
- nic_ens102f1_stat         (string/boolean)
- nic_enP1s125f0np0_stat    (string/boolean)
- nic_enP1s125f1np1_stat    (string/boolean)
- nic_enxfef11ad36eb7_stat  (string/boolean)
- nic_enxee7c7c859844_stat  (string/boolean)


[Infiniband / IB]
- ib_nic_temp               (°C)       IB NIC chipset temperature

[Cooling - coolant]
- coolant_temp_inlet1       (°C)       coolant inlet temperature (channel1)
- coolant_temp_inlet2       (°C)       coolant inlet temperature (channel2)
- coolant_temp_outlet1      (°C)       coolant outlet temperature (channel1)
- coolant_temp_outlet2      (°C)       coolant outlet temperature (channel2)
- coolant_delta_t1          (°C)       ΔT = outlet1 - inlet1
- coolant_delta_t2          (°C)       ΔT = outlet2 - inlet2
- coolant_level             (0/1 bool) coolant level (0 Low, 1 High) 
- coolant_leak              (0/1 bool) coolant leakage detection (0 Noraml, 1 Leak detected) 

[Air / Environment]
- air_temp                  (°C)       internal air temperature
- air_humit                 (%RH)      internal air relative humidity

[Host]
- host_stat (0/1 bool) host server status check (0: offline, 1 online)

"""


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

        # Cooling
        g.add_metric([srv, "cooling", "leak_detected", "bool", ""], get_int("coolant_leak"))
        g.add_metric([srv, "cooling", "level_full", "bool", ""], get_int("coolant_level"))
        for ch in ["1", "2"]:
            g.add_metric([srv, "cooling", f"inlet{ch}_temp", "°C", ""], get_float(f"coolant_temp_inlet{ch}"))
            g.add_metric([srv, "cooling", f"outlet{ch}_temp", "°C", ""], get_float(f"coolant_temp_outlet{ch}"))
            g.add_metric([srv, "cooling", f"delta_t{ch}", "°C", ""], get_float(f"coolant_delta_t{ch}"))

        # Environment
        g.add_metric([srv, "environment", "air_temp", "°C", ""], get_float("air_temp"))
        g.add_metric([srv, "environment", "air_humidity", "%RH", ""], get_float("air_humit"))

        # GPUs (0~7)
        for i in range(8):
            name_bytes = client.get(f"gpu_name_{i}")
            gpu_name = name_bytes.strip() if name_bytes else f"GPU{i}"
            extra = gpu_name.replace(" ", "_").replace("/", "-").replace(",", "").replace("(", "").replace(")", "")
            temp = get_float(f"gpu_temp_{i}")
            pwr = get_float(f"gpu_curr_pwr_{i}")
            pwr_limit = get_float(f"gpu_max_pwr_{i}")
            mem_used = get_float(f"gpu_curr_mem_{i}")
            mem_total = get_float(f"gpu_max_mem_{i}")
            mem_available_pct = (mem_used / mem_total * 100) if mem_total > 0 else 0.0
            g.add_metric([srv, f"gpu{i}", "temperature", "°C", extra], temp)
            g.add_metric([srv, f"gpu{i}", "power_current", "W", extra], pwr)
            g.add_metric([srv, f"gpu{i}", "power_limit", "W", extra], pwr_limit)
            g.add_metric([srv, f"gpu{i}", "memory_used", "MiB", extra], mem_used)
            g.add_metric([srv, f"gpu{i}", "memory_total", "MiB", extra], mem_total)
            g.add_metric([srv, f"gpu{i}", "memory_available", "%", extra], mem_available_pct)

        # CPU
        g.add_metric([srv, "cpu", "usage_total", "%", ""], get_float("cpu_usage"))
        for i in [0, 1]:
            g.add_metric([srv, f"cpu{i}", "temperature", "°C", ""], get_float(f"cpu_temp_{i}"))
            g.add_metric([srv, f"cpu{i}", "power", "W", ""], get_float(f"cpu_curr_pwr_{i}"))

        # System Memory
        g.add_metric([srv, "memory", "total", "GiB", ""], get_float("mem_total"))
        g.add_metric([srv, "memory", "available", "GiB", ""], get_float("mem_available"))
        g.add_metric([srv, "memory", "usage", "GiB", ""], get_float("mem_usage"))

        # Network 
        nic_keys = client.keys("nic_*_stat")
        seen_nics = set()

        for key in nic_keys:
            if not key.startswith("nic_") or not key.endswith("_stat"):
                continue
            nic = key[4:-5]  
            if nic in seen_nics:
                continue
            seen_nics.add(nic)

            val = get_int(key)
            g.add_metric([srv, "network", "link_status", "1=up", nic], val)

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
