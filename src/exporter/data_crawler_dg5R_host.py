#!/usr/bin/python
# -*- coding:utf-8 -*-
"""
data_crawler_dg5R_host.py
Runs on the HOST machine (dg5R server).
Collects CPU, GPU, Memory, Network metrics and pushes to local Redis.
serial_sender_v2.py will relay these to gadgetini (Raspberry Pi).
"""
import redis

rd = redis.StrictRedis(host='localhost', port=6379, db=0)

'''
         Key                          : Value                      : Source
------------------------------------------------------------------------------------------
  CPU
    cpu_0                             : JSON  {"Tctl": {"temp1_input": float}}  : lm-sensors
    cpu_1                             : JSON  {"Tctl": {"temp1_input": float}}  : lm-sensors
    cpu_util                          : float (%)                  : psutil
    cpu_power_0                       : float (W)                  : RAPL
    cpu_power_1                       : float (W)                  : RAPL

  GPU (per device, index N = 0,1,...,7)
    gpuN                              : JSON  {"name": str,                     : nvidia-smi
                                               "temperature": float,
                                               "utilization_gpu": float,
                                               "utilization_memory": float,
                                               "power.draw": float,
                                               "power.limit": float,
                                               "memory.used": float (bytes),
                                               "memory.total": float (bytes)}

  Memory
    memory                            : JSON  {"total_memory_gb": float,        : psutil
                                               "available_memory_gb": float,
                                               "used_memory_gb": float,
                                               "swap_total_gb": float,
                                               "swap_used_gb": float,
                                               "swap_free_gb": float}
    oom_count                         : int                        : dmesg

  Network
    net_link_status                   : int   (1=UP, 0=DOWN)       : psutil
    net_tx_bps                        : float (Gbps)               : psutil
    net_rx_bps                        : float (Gbps)               : psutil
    net_errors_rate                   : float (%)                  : psutil
    net_drops_rate                    : float (%)                  : psutil
    net_nic_name                      : str                        : psutil
'''

while True:
    # CPU
    collect_cpu_temps()
    collect_cpu_util()
    collect_cpu_power()

    # GPU
    collect_gpu_metrics()

    # Memory
    collect_memory_metrics()
    collect_oom_count()

    # Network
    collect_network_metrics()
