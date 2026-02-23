#!/usr/bin/env python
# -*- coding: utf-8 -*-
# deepgadget Monitoring Agent (v0.4)
#
# This code collects basic host hardware/resource metrics (e.g., CPU, memory, disk, network)
# and forwards them to the deepgadget monitoring system for observability purposes.
#
# It is intended for monitoring only: it does not control, modify, or tune host resources,
# and it should not be interpreted as performing benchmarking or enforcing limits.

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
from typing import List, Dict
import os
client = redis.StrictRedis(host='fd12:3456:789a:1::2', port=6379, db=0)

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

def get_nvidia_gpu_telemetry():
    result = subprocess.Popen(["nvidia-smi", "--query-gpu=name,temperature.gpu,power.draw,power.limit,memory.used,memory.total","--format=csv,noheader,nounits"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    output, errors = result.communicate() # results generate 1 single string
    gpus = output.split("\n")# split single gpu info by \n, 
    gpus.pop()# and remove useless blank at last.
    gpus_info = []
    for i in gpus: gpus_info.append(i.split(", "))
    return gpus_info # 2-dim array

#print(get_nvidia_gpu_telemetry())
#exit()


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

def parse_cpu_telemetry(sensors_data):
    cpusinfo = []
    temp_list = []
    package_temp_list = []
    pattern = r"(k10temp-pci-[a-f0-9]+|coretemp-isa-[0-9]+)"

    for key in sensors_data.keys():
        cpukey_match = re.search(pattern, key)
        if cpukey_match:
            cpu_metric = sensors_data[key]
            cpusinfo.append(cpu_metric)
    for cpu in cpusinfo:
        tctl = cpu.get('Tctl', {})
        if 'temp1_input' in tctl:
            if tctl['temp1_input'] > 50:
                temp_list.append(round(tctl['temp1_input'] - 25, 1))
            else:
                temp_list.append(round(tctl['temp1_input'], 1))
        for metric_name, metric_value in cpu.items():
            if re.search(r"Package id \d+", metric_name) and isinstance(metric_value, dict):
                pkg_temp = metric_value.get('temp1_input')
                if pkg_temp is not None:
                    package_temp_list.append(round(pkg_temp, 1))
    #print("cpusinfo", cpusinfo)
    cpusinfo = [temp_list, package_temp_list]
    #print("cpusinfo", cpusinfo)
    print("cpusinfo", package_temp_list)
    return cpusinfo

def get_CPU_telemetry(sensors=None, sensors_output=None):
    if sensors_output is not None:
        if isinstance(sensors_output, str):
            sensors_data = json.loads(sensors_output)
        elif isinstance(sensors_output, dict):
            sensors_data = sensors_output
        else:
            raise TypeError("sensors_output must be a JSON string or dict")
    else:
        if sensors is None:
            raise ValueError("sensors process handle is required when sensors_output is not provided")
        output, errors = sensors.communicate()
        sensors_data = json.loads(output)

    return parse_cpu_telemetry(sensors_data)


def get_ipmi_power_output():
    """
    Launch ipmitool process to read CPU power sensors (POWER_CPU1, POWER_CPU2).
    Returns a subprocess.Popen handle.
    """
    return subprocess.Popen(
        ["ipmitool", "sensor", "reading", "POWER_CPU1", "POWER_CPU2"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

def parse_cpu_power_telemetry(ipmi_text: str):
    """
    Parse ipmitool text output and extract POWER_CPU1/POWER_CPU2 readings as float Watts.

    Supported formats:
      A) Two-column output (your current output):
         POWER_CPU1 | 82
         POWER_CPU2 | 86

      B) Typical `sensor reading` with unit:
         POWER_CPU1 | 82.000 | Watts | ok

      C) Typical `sdr elist` style:
         POWER_CPU1 | ... | 82 Watts

    Returns:
      {"cpu1_watts": float|None, "cpu2_watts": float|None}
    """
    result = {"cpu_curr_pwr_0": None, "cpu_curr_pwr_1": None}

    for line in ipmi_text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Match lines starting with POWER_CPU1 or POWER_CPU2 and capture the rest
        m = re.match(r"^(POWER_CPU[12])\s*\|\s*(.+)$", line)
        if not m:
            continue

        sensor_name = m.group(1)
        rest = m.group(2).strip()

        watts = None

        # Case 1: Two-column output where `rest` is a plain number (e.g., "82")
        mn = re.match(r"^([0-9]+(?:\.[0-9]+)?)$", rest)
        if mn:
            watts = float(mn.group(1))
        else:
            # Case 2: "82 Watts" appears somewhere in the remainder
            mw = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*Watts\b", rest, re.IGNORECASE)
            if mw:
                watts = float(mw.group(1))
            else:
                # Case 3: Multi-column format: "82.000 | Watts | ok"
                parts = [p.strip() for p in rest.split("|")]
                if parts and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", parts[0]):
                    watts = float(parts[0])

        # Assign parsed value to the proper output field
        if watts is not None:
            if sensor_name.endswith("1"):
                result["cpu_curr_pwr_0"] = watts
            else:
                result["cpu_curr_pwr_1"] = watts

    return result

def get_CPU_power_telemetry(ipmi_proc=None, ipmi_output=None):
    """
    Fetch and parse CPU power telemetry.

    Usage patterns:
      - If ipmi_output is provided (string), parse it directly.
      - Otherwise, ipmi_proc must be a subprocess.Popen handle and we read stdout/stderr.

    Returns:
      {"cpu1_watts": float|None, "cpu2_watts": float|None}
    """
    if ipmi_output is not None:
        if not isinstance(ipmi_output, str):
            raise TypeError("ipmi_output must be a string")
        text = ipmi_output
    else:
        if ipmi_proc is None:
            raise ValueError("ipmi_proc is required when ipmi_output is not provided")

        out, err = ipmi_proc.communicate()
        if ipmi_proc.returncode not in (0, None) and not out:
            raise RuntimeError(f"ipmitool failed: {err.strip()}")
        text = out

    return parse_cpu_power_telemetry(text)


# Example:
# ipmi = get_ipmi_power_output()
# power = get_CPU_power_telemetry(ipmi_proc=ipmi)
# print(power)  # {"cpu1_watts": 82.0, "cpu2_watts": 86.0}

def get_nic_link_status() -> List[Dict[str, int]]:
    """
    Return NIC link status using only `ip link show` output.

    - Excludes loopback interface "lo"
    - Uses LOWER_UP flag as physical link indicator
    - Returns 1 for link up, 0 for link down

    Return format:
        [
          {"ens102f1": 1},
          {"enp1s0": 0},
          ...
        ]
    """
    res = subprocess.run(["ip", "-o", "link", "show"], capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"ip link show failed (rc={res.returncode}): {(res.stderr or res.stdout).strip()}")

    out: List[Dict[str, int]] = []

    for line in (res.stdout or "").splitlines():
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue

        dev = parts[1].strip().split("@", 1)[0]
        if not dev or dev == "lo":
            continue

        rest = parts[2]
        flags = rest[rest.find("<") + 1 : rest.find(">")] if "<" in rest and ">" in rest else ""
        flags_list = [f.strip() for f in flags.split(",") if f.strip()]

        link_up = 1 if "LOWER_UP" in flags_list else 0
        out.append({dev: link_up})

    return out


def get_ib_nic_asic_temp(mst_dev: str = "/dev/mst/mt4129_pciconf0") -> int:
    """
    Returns Mellanox/NVIDIA IB NIC ASIC temperature (°C) by running:
      sudo mget_temp -d <mst_dev>
    Example output: "42"
    """
    p = subprocess.run(
        ["sudo", "mget_temp", "-d", mst_dev],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=3,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"mget_temp failed (rc={p.returncode}): {p.stderr.strip()}")

    out = p.stdout.strip()
    try:
        return str(out)
    except ValueError as e:
        raise RuntimeError(f"unexpected mget_temp output: {out!r}") from e

if __name__ == "__main__":
    while True:
        sensors  = get_sensors_output()
        ipmi = get_ipmi_power_output()
        #curr_chipsinfo = get_amd_gpu_telemetry(sensors)
        curr_chipsinfo = get_nvidia_gpu_telemetry() 
        curr_cpusinfo = get_CPU_telemetry(sensors)
        curr_meminfo = get_memory_usage_mb()
        curr_ipmi_telemetry = get_CPU_power_telemetry(ipmi_proc=ipmi)
        curr_link_status = get_nic_link_status()
        # lpush for multi socket cpu, multi gpu 
        for idx, cpu in enumerate(curr_cpusinfo[1]):
            print("cpu_temp_" + str(idx), str(cpu))
            client.set("cpu_temp_" + str(idx), str(cpu))
        # ipmi cpu power
        for idx, key in enumerate(curr_ipmi_telemetry):
            client.set(str(key), str(curr_ipmi_telemetry[key]))
            print(curr_ipmi_telemetry)
            print(key)
            print(curr_ipmi_telemetry[key])
		# nic link status
        for nic in curr_link_status:
            key ,val = next(iter(nic.items()))
            client.set("nic_"+str(key)+"_stat", str(val))
            print(key)
            print(val)
        for idx, gpu in enumerate(curr_chipsinfo):
            client.set("gpu_name_" + str(idx), str(gpu[0]))
        
        # temperature
        for idx, gpu in enumerate(curr_chipsinfo):
            client.set("gpu_temp_" + str(idx), str(gpu[1]))

        # current_pwr_usage
        for idx, gpu in enumerate(curr_chipsinfo):
            client.set("gpu_curr_pwr_" + str(idx), str(gpu[2]))

        # max_pwr
        for idx, gpu in enumerate(curr_chipsinfo):
            client.set("gpu_max_pwr_" + str(idx), str(gpu[3]))

        # current_memory_usage
        for idx, gpu in enumerate(curr_chipsinfo):
            client.set("gpu_curr_mem_" + str(idx), str(gpu[4]))

        # max_memory
        for idx, gpu in enumerate(curr_chipsinfo):
            client.set("gpu_max_mem_" + str(idx), str(gpu[5]))

        client.set("mem_total", curr_meminfo[0])
        client.set("mem_usage", curr_meminfo[1])
        client.set("mem_available", curr_meminfo[2])
        client.set("cpu_usage", get_cpu_usage_percent())
        client.set("ib_nic_temp", get_ib_nic_asic_temp())
