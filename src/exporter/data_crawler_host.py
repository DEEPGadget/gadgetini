#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import re
import subprocess
import time
from typing import Dict, List

import redis


REDIS_HOST = os.environ.get("GADGETINI_REDIS_HOST", "fd12:3456:789a:1::2")
REDIS_PORT = int(os.environ.get("GADGETINI_REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("GADGETINI_REDIS_DB", "0"))

client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

NVME_KEY_TTL_SEC = 60


def get_sensors_json() -> dict:
    p = subprocess.run(
        ["sensors", "-j"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=5,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"sensors -j failed: {p.stderr.strip()}")
    return json.loads(p.stdout)


def get_sensors_text() -> str:
    p = subprocess.run(
        ["sensors"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=5,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"sensors failed: {p.stderr.strip()}")
    return p.stdout


def get_memory_usage_mb():
    meminfo = {}

    with open("/proc/meminfo", "r") as f:
        for line in f:
            key, value = line.split(":", 1)
            meminfo[key] = int(value.strip().split()[0])

    mem_total = meminfo.get("MemTotal", 0)
    mem_available = meminfo.get("MemAvailable", 0)
    mem_used = mem_total - mem_available

    return [
        round(mem_total / (1024 * 1024), 1),
        round(mem_used / (1024 * 1024), 1),
        round(mem_available / (1024 * 1024), 1),
    ]


def get_cpu_usage_percent(interval=0.5):
    def read_cpu_times():
        with open("/proc/stat", "r") as f:
            for line in f:
                if line.startswith("cpu "):
                    values = list(map(int, line.split()[1:]))
                    total = sum(values)
                    idle = values[3] + values[4]
                    return total, idle
        return 0, 0

    total1, idle1 = read_cpu_times()
    time.sleep(interval)
    total2, idle2 = read_cpu_times()

    delta_total = total2 - total1
    delta_idle = idle2 - idle1

    if delta_total == 0:
        return 0.0

    return round((1 - delta_idle / delta_total) * 100, 1)


def get_nvidia_gpu_telemetry():
    p = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,temperature.gpu,power.draw,power.limit,memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
        check=False,
    )

    if p.returncode != 0 or not p.stdout.strip():
        return []

    gpus_info = []
    for line in p.stdout.strip().splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) >= 6:
            gpus_info.append(parts[:6])

    return gpus_info


def parse_cpu_telemetry(sensors_data):
    temp_list = []
    package_temp_list = []

    pattern = r"(k10temp-pci-[a-f0-9]+|coretemp-isa-[0-9]+)"

    for key, metrics in sensors_data.items():
        if not re.search(pattern, key):
            continue
        if not isinstance(metrics, dict):
            continue

        tctl = metrics.get("Tctl", {})
        if isinstance(tctl, dict) and "temp1_input" in tctl:
            temp = float(tctl["temp1_input"])
            if temp > 50:
                temp_list.append(round(temp - 25, 1))
            else:
                temp_list.append(round(temp, 1))

        for metric_name, metric_value in metrics.items():
            if re.search(r"Package id \d+", metric_name) and isinstance(metric_value, dict):
                pkg_temp = metric_value.get("temp1_input")
                if pkg_temp is not None:
                    package_temp_list.append(round(float(pkg_temp), 1))

    effective_temp_list = package_temp_list if package_temp_list else temp_list
    return [temp_list, effective_temp_list]


def get_cpu_telemetry(sensors_data):
    return parse_cpu_telemetry(sensors_data)


def get_ipmi_power_output():
    return subprocess.run(
        ["ipmitool", "sensor", "reading", "POWER_CPU1", "POWER_CPU2"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=5,
        check=False,
    )


def parse_cpu_power_telemetry(ipmi_text: str):
    result = {"cpu_curr_pwr_0": None, "cpu_curr_pwr_1": None}

    for line in ipmi_text.splitlines():
        line = line.strip()
        if not line:
            continue

        m = re.match(r"^(POWER_CPU[12])\s*\|\s*(.+)$", line)
        if not m:
            continue

        sensor_name = m.group(1)
        rest = m.group(2).strip()

        watts = None

        mn = re.match(r"^([0-9]+(?:\.[0-9]+)?)$", rest)
        if mn:
            watts = float(mn.group(1))
        else:
            mw = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*Watts\b", rest, re.IGNORECASE)
            if mw:
                watts = float(mw.group(1))
            else:
                parts = [p.strip() for p in rest.split("|")]
                if parts and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", parts[0]):
                    watts = float(parts[0])

        if watts is not None:
            if sensor_name.endswith("1"):
                result["cpu_curr_pwr_0"] = watts
            else:
                result["cpu_curr_pwr_1"] = watts

    return result


def parse_cpu_power_from_sensors(sensors_data):
    result = {"cpu_curr_pwr_0": None, "cpu_curr_pwr_1": None}
    pattern = r"(k10temp-pci-[a-f0-9]+|coretemp-isa-[0-9]+|amd_hsmp_hwmon-isa-[0-9]+)"

    cpu_idx = 0

    for key, metrics in sensors_data.items():
        if not re.search(pattern, key):
            continue
        if not isinstance(metrics, dict):
            continue

        for metric_value in metrics.values():
            if not isinstance(metric_value, dict):
                continue

            for field, val in metric_value.items():
                if "power" in field and "input" in field and val is not None:
                    result[f"cpu_curr_pwr_{cpu_idx}"] = round(float(val), 1)
                    cpu_idx += 1
                    if cpu_idx >= 2:
                        return result

    return result


def get_cpu_power_telemetry(sensors_data):
    try:
        ipmi = get_ipmi_power_output()
        if ipmi.stdout:
            result = parse_cpu_power_telemetry(ipmi.stdout)
            if any(v is not None for v in result.values()):
                return result
    except Exception:
        pass

    try:
        return parse_cpu_power_from_sensors(sensors_data)
    except Exception:
        return {"cpu_curr_pwr_0": None, "cpu_curr_pwr_1": None}


def get_nic_link_status() -> List[Dict[str, int]]:
    p = subprocess.run(
        ["ip", "-o", "link", "show"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=5,
        check=False,
    )

    if p.returncode != 0:
        return []

    out = []

    for line in p.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue

        dev = parts[1].strip().split("@", 1)[0]
        if not dev or dev == "lo":
            continue

        rest = parts[2]
        flags = rest[rest.find("<") + 1:rest.find(">")] if "<" in rest and ">" in rest else ""
        flags_list = [f.strip() for f in flags.split(",") if f.strip()]

        link_up = 1 if "LOWER_UP" in flags_list else 0
        out.append({dev: link_up})

    return out


def get_ib_nic_asic_temp(mst_dev: str = "/dev/mst/mt4129_pciconf0"):
    p = subprocess.run(
        ["sudo", "mget_temp", "-d", mst_dev],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=3,
        check=False,
    )

    if p.returncode != 0:
        return None

    out = p.stdout.strip()
    return out if out else None


def get_nvme_temps_from_text(text: str) -> dict:
    """
    NVMe는 plain `sensors` 출력 기준 Composite 줄만 읽는다.

    예:
      nvme-pci-6d00
      Adapter: PCI adapter
      Composite:    +39.9°C
    """
    result = {}
    nvme_list = []
    current_device = None

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("nvme-pci-"):
            current_device = line.split()[0]
            continue

        if current_device and line.startswith("Composite:"):
            m = re.search(r"Composite:\s*\+?([-+]?[0-9]+(?:\.[0-9]+)?)\s*°?C", line)
            if m:
                nvme_list.append((current_device, round(float(m.group(1)), 1)))
            current_device = None

    nvme_list.sort(key=lambda x: x[0])

    for idx, (name, temp) in enumerate(nvme_list):
        result[f"nvme_{idx}_name"] = name
        result[f"nvme_{idx}_temp"] = temp

    return result


def clear_stale_nvme_keys(pipe, current_count):
    old_indexes = set()

    for raw_key in client.keys("nvme_*_temp"):
        key_s = raw_key.decode() if isinstance(raw_key, bytes) else str(raw_key)
        m = re.fullmatch(r"nvme_(\d+)_temp", key_s)
        if m:
            old_indexes.add(int(m.group(1)))

    for old_idx in sorted(i for i in old_indexes if i >= current_count):
        pipe.delete(f"nvme_{old_idx}_temp", f"nvme_{old_idx}_name")


def write_metrics_once():
    sensors_data = get_sensors_json()
    sensors_text = get_sensors_text()

    curr_chipsinfo = get_nvidia_gpu_telemetry()
    curr_cpusinfo = get_cpu_telemetry(sensors_data)
    curr_meminfo = get_memory_usage_mb()
    curr_ipmi_telemetry = get_cpu_power_telemetry(sensors_data)
    curr_link_status = get_nic_link_status()
    curr_nvme_temps = get_nvme_temps_from_text(sensors_text)

    pipe = client.pipeline(transaction=False)

    # CPU temperature
    for idx, cpu in enumerate(curr_cpusinfo[1]):
        pipe.set(f"cpu_temp_{idx}", str(cpu))

    # CPU power
    for key, value in curr_ipmi_telemetry.items():
        if value is not None:
            pipe.set(str(key), str(value))

    # NIC link
    for nic in curr_link_status:
        key, val = next(iter(nic.items()))
        pipe.set(f"nic_{key}_stat", str(val))

    # GPU
    for idx, gpu in enumerate(curr_chipsinfo):
        pipe.set(f"gpu_name_{idx}", str(gpu[0]))
        pipe.set(f"gpu_temp_{idx}", str(gpu[1]))
        pipe.set(f"gpu_curr_pwr_{idx}", str(gpu[2]))
        pipe.set(f"gpu_max_pwr_{idx}", str(gpu[3]))
        pipe.set(f"gpu_curr_mem_{idx}", str(gpu[4]))
        pipe.set(f"gpu_max_mem_{idx}", str(gpu[5]))

    # Memory / CPU usage
    pipe.set("mem_total", curr_meminfo[0])
    pipe.set("mem_usage", curr_meminfo[1])
    pipe.set("mem_available", curr_meminfo[2])
    pipe.set("cpu_usage", get_cpu_usage_percent())

    # IB NIC
    ib_temp = get_ib_nic_asic_temp()
    if ib_temp is not None:
        pipe.set("ib_nic_temp", ib_temp)

    # NVMe
    nvme_count = 0

    for key, value in curr_nvme_temps.items():
        pipe.set(str(key), str(value), ex=NVME_KEY_TTL_SEC)
        if str(key).endswith("_temp"):
            nvme_count += 1

    pipe.set("nvme_count", str(nvme_count), ex=NVME_KEY_TTL_SEC)
    clear_stale_nvme_keys(pipe, nvme_count)

    # Host heartbeat
    pipe.set("host_ttl", int(time.time() * 1000))
    pipe.expire("host_ttl", 7)

    pipe.execute()


if __name__ == "__main__":
    while True:
        try:
            write_metrics_once()
        except Exception as e:
            print(f"[ERROR] data_crawler_host failed: {e}", flush=True)

        time.sleep(1)