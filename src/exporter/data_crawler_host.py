#!/usr/bin/env python
# -*- coding: utf-8 -*-

import redis
import json
import jsons
import subprocess
import re
from rich.live import Live
from rich.text import Text
from rich.console import Group
import time
import math

client = redis.StrictRedis(host='localhost', port=6379, db=0)

def get_sensors_output():
    result = subprocess.Popen(["sensors", "-j"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result

def get_memory_usage_mb():
    meminfo = {}
    memoutput = []
    with open("/proc/meminfo", "r") as f:
        for line in f:
            parts = line.split(":")
            key = parts[0]
            value = parts[1].strip().split()[0]
            meminfo[key] = int(value)
    mem_total = meminfo.get("MemTotal",0)
    mem_available = meminfo.get("MemAvailable",0)
    mem_used = mem_total - mem_available
    memoutput.append(round(mem_total / (1024 * 1024),1))
    memoutput.append(round(mem_used / (1024 * 1024),1))
    memoutput.append(round(mem_available / (1024 * 1024),1))
#    for val in memoutput:
#        ##print(val)
#        ##print(type(val))
#    exit()
    return memoutput

def get_cpu_usage_percent(interval=0.5):
    def read_cpu_times():
        with open("/proc/stat", "r") as f:
            for line in f:
                if line.startswith("cpu"):
                    parts = line.split()
                    values = list(map(int, parts[1:]))
                    total = sum(values)
                    idle = values[3] + values[4]
                    return total, idle
        return 0,0
    total1, idle1 = read_cpu_times()
    time.sleep(interval)
    total2, idle2 = read_cpu_times()

    delta_total = total2 - total1
    delta_idle = idle2 - idle1
    if delta_total == 0:
        return 0.0
    usage = (1 - delta_idle / delta_total) * 100
    return round(usage, 1)

def get_amd_gpu_telemetry(sensors):
    chipsinfo = []
    asic_temp_list = []
    mem_temp_list = []
    pwr_list = []
   
    output, errors = sensors.communicate()
    sensors_data = json.loads(output)
    for device, metrics in sensors_data.items():
        if device.startswith("amdgpu-pci-"):
            edge_temp = metrics.get("edge", {}).get("temp1_input")
            mem_temp = metrics.get("mem", {}).get("temp3_input")
            power_avg = metrics.get("PPT", {}).get("power1_average")
            asic_temp_list.append(round(edge_temp, 1) if edge_temp is not None else None)
            mem_temp_list.append(round(mem_temp, 1) if mem_temp is not None else None)
            pwr_list.append(round(power_avg, 1) if power_avg is not None else None)
    chipsinfo = [asic_temp_list, mem_temp_list, pwr_list]
    return chipsinfo

def get_TT_telemetry(sensors):
    chipsinfo = []
    temp_list = []
    pwr_list = []
    pattern = r"wormhole-pci-[a-f0-9]"
    output, errors = sensors.communicate()
    sensors_data = json.loads(output)

    for key in sensors_data.keys():
        whkey_match = re.search(pattern, key)
        if whkey_match:
            wh_metric = sensors_data[key]
            chipsinfo.append(wh_metric)
    for chip_id, chip in enumerate(chipsinfo):
        temp_list.append(round(chip["asic1_temp"]["temp1_input"], 1))
        pwr_list.append(chip["power1"]["power1_input"])
    chipsinfo = [temp_list, pwr_list]
    return chipsinfo

def get_CPU_telemetry(sensors):
    cpusinfo = []
    temp_list = []
    pattern = r"k10temp-pci-[a-f0-9]"
    output, errors = sensors.communicate()
    sensors_data = json.loads(output)

    for key in sensors_data.keys():
        cpukey_match = re.search(pattern, key)
        if cpukey_match:
            cpu_metric = sensors_data[key]
            cpusinfo.append(cpu_metric)
    for cpu_id, cpu in enumerate(cpusinfo):
        if cpu['Tctl']['temp1_input'] > 50:
            temp_list.append(round(cpu['Tctl']['temp1_input']-25, 1))
        else:
            temp_list.append(round(cpu['Tctl']['temp1_input'], 1))
    ##print("cpusinfo", cpusinfo)
    cpusinfo = [temp_list]
    ##print("cpusinfo", cpusinfo)
    return cpusinfo


if __name__ == "__main__":
#    init = 0
    while True:
        sensors  = get_sensors_output()
        curr_chipsinfo = get_amd_gpu_telemetry(sensors)
        curr_cpusinfo = get_CPU_telemetry(sensors)
        curr_meminfo = get_memory_usage_mb()
        ##print(curr_cpusinfo)

        # lpush for multi socket cpu, multi gpu 
        for idx, cpu in enumerate(curr_cpusinfo[0]):
            #print("cpu_temp_" + str(idx), str(cpu))
            client.set("cpu_temp_" + str(idx), str(cpu))

        for idx, temp in enumerate(curr_chipsinfo[0]):
            #print("9070_temp_"+ str(idx), temp)
            client.set("9070XT_asic_temp_" + str(idx), str(temp))

        for idx, temp in enumerate(curr_chipsinfo[1]):
            #print("9070_mem_temp_" + str(idx), temp)
            client.set("9070XT_mem_temp_" + str(idx), str(temp))

        for idx, pwr in enumerate(curr_chipsinfo[2]):
            #print("9070_pwr_" + str(idx), pwr)
            client.set("9070XT_pwr_" + str(idx), str(temp))

        client.set("mem_total", curr_meminfo[0])
        client.set("mem_usage", curr_meminfo[1])
        client.set("mem_available", curr_meminfo[2])
        client.set("cpu_usage", get_cpu_usage_percent())
           
#        if init == 1:
#            client.ltrim("cpu_temp",len(curr_cpusinfo), -1)
#            client.ltrim("9070XT_asic_temp",len(curr_chipsinfo[0]), -1)
#            client.ltrim("9070XT_mem_temp",len(curr_chipsinfo[1]), -1)
#            client.ltrim("9070XT_pwr",len(curr_chipsinfo[2]), -1)
            #client.ltrim("mem_total", 1, -1)
            #client.ltrim("mem_usage", 1, -1)
            #client.ltrim("mem_available", 1, -1)

#       init = 1
        ##print(client.get("9070XT_asic_temp_0"))
        ##print("current mem_usage_redis_query")
        ###print(client.lrange("mem_usage",0,-1))
        ##print(client.get("mem_usage"))
