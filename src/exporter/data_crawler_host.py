#!/usr/bin/env python
# -*- coding: utf-8 -*-

import fcntl
import json
import os
import re
import struct
import subprocess
import time
from typing import Dict, List

import redis


REDIS_HOST = os.environ.get("GADGETINI_REDIS_HOST", "fd12:3456:789a:1::2")
REDIS_PORT = int(os.environ.get("GADGETINI_REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("GADGETINI_REDIS_DB", "0"))

client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

NVME_KEY_TTL_SEC = 60
# gpu_*/npu_* keys expire so a removed chip or a stopped host shows up as an
# absent key, which sensor_exporter skips instead of exporting stale values.
CHIP_KEY_TTL_SEC = 60


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
    # A host may carry only NPUs: a missing nvidia-smi must not abort the whole
    # write_metrics_once() cycle (FileNotFoundError used to escape from here).
    try:
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
    except (subprocess.TimeoutExpired, OSError):
        return []

    if p.returncode != 0 or not p.stdout.strip():
        return []

    gpus_info = []
    for line in p.stdout.strip().splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) >= 6:
            gpus_info.append(parts[:6])

    return gpus_info


# FuriosaAI NPU (RNGD) via furiosa-smi. It has no machine-readable output mode,
# so the box-drawn tables of `info` and `status` are parsed by header name:
#   | Arch | Device | Firmware | Temp.   | Power    | PCI-BDF |
#   | rngd | npu0   | ...      | 55.25°C | 144.00 W | ...     |
# `status` spreads a device over several lines (one per core); only the line
# whose Device cell is filled carries the Memory value ("0.00/47.50 GiB").
def run_furiosa_smi(args) -> str:
    try:
        p = subprocess.run(
            ["furiosa-smi", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""

    if p.returncode != 0:
        return ""
    return p.stdout


def parse_smi_table(text: str) -> List[Dict[str, str]]:
    header = None
    rows = []

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue

        cells = [c.strip() for c in line.strip("|").split("|")]

        if header is None:
            if "Device" in cells:
                header = cells
            continue

        if len(cells) != len(header):
            continue

        row = dict(zip(header, cells))
        if row.get("Device"):
            rows.append(row)

    return rows


_NUM_RE = r"[-+]?[0-9]+(?:\.[0-9]+)?"
_MEM_UNIT_TO_MIB = {"KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "TiB": 1024 * 1024}


def _first_number(text: str):
    m = re.search(_NUM_RE, text or "")
    return float(m.group(0)) if m else None


def get_furiosa_npu_telemetry() -> Dict[int, dict]:
    """{npu index: {name, temp, power[, mem_used, mem_total]}}; memory in MiB
    to match nvidia-smi. Empty when furiosa-smi is absent or fails."""
    npus = {}

    for row in parse_smi_table(run_furiosa_smi(["info"])):
        m = re.fullmatch(r"npu(\d+)", row.get("Device", ""))
        if not m:
            continue
        temp = _first_number(row.get("Temp.", ""))
        power = _first_number(row.get("Power", ""))
        if temp is None:
            continue
        npus[int(m.group(1))] = {
            "name": (row.get("Arch") or "npu").upper(),
            "temp": round(temp, 1),
            "power": round(power, 1) if power is not None else None,
        }

    if not npus:
        return npus

    for row in parse_smi_table(run_furiosa_smi(["status"])):
        m = re.fullmatch(r"npu(\d+)", row.get("Device", ""))
        if not m or int(m.group(1)) not in npus:
            continue
        mm = re.search(
            rf"({_NUM_RE})\s*/\s*({_NUM_RE})\s*(KiB|MiB|GiB|TiB)", row.get("Memory", "")
        )
        if not mm:
            continue
        scale = _MEM_UNIT_TO_MIB[mm.group(3)]
        npus[int(m.group(1))]["mem_used"] = round(float(mm.group(1)) * scale, 1)
        npus[int(m.group(1))]["mem_total"] = round(float(mm.group(2)) * scale, 1)

    return npus


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
        # Single-socket boards expose POWER_CPU, dual-socket ones POWER_CPU1/2.
        # ipmitool resolves each name independently: missing ones only produce a
        # "not found!" line on stderr, the rest still print to stdout.
        ["ipmitool", "sensor", "reading", "POWER_CPU", "POWER_CPU1", "POWER_CPU2"],
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

        m = re.match(r"^(POWER_CPU[12]?)\s*\|\s*(.+)$", line)
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
            if sensor_name == "POWER_CPU2":
                result["cpu_curr_pwr_1"] = watts
            else:
                result["cpu_curr_pwr_0"] = watts

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


# AMD HSMP (Host System Management Port) — third-tier source for boards that
# expose CPU power through neither the BMC nor hwmon: Threadripper PRO / EPYC
# platforms such as the ASUS Pro WS WRX90E-SAGE SE have no POWER_CPU* entry in
# the SDR and no power*_input under k10temp. Needs the amd_hsmp module loaded
# (/dev/hsmp); absent that, the probe is a single os.path.exists() and returns.
HSMP_DEV = "/dev/hsmp"
# struct hsmp_message: u32 msg_id, u16 num_args, u16 response_sz,
#                      u32 args[8], u16 sock_ind, 2 bytes tail padding = 44 B
HSMP_MSG_FMT = "=IHH8IH2x"
HSMP_IOCTL = 0xC02CF800  # _IOWR(0xF8, 0, struct hsmp_message)
HSMP_GET_SOCKET_POWER = 4


def read_hsmp_socket_power_mw(sock_ind: int) -> int:
    """Current socket power in mW. Raises OSError(ENODEV) for absent sockets."""
    buf = bytearray(
        struct.pack(HSMP_MSG_FMT, HSMP_GET_SOCKET_POWER, 0, 1, *([0] * 8), sock_ind)
    )

    fd = os.open(HSMP_DEV, os.O_RDWR)
    try:
        fcntl.ioctl(fd, HSMP_IOCTL, buf, True)
    finally:
        os.close(fd)

    # The reply is written back into args[0].
    return struct.unpack(HSMP_MSG_FMT, bytes(buf))[3]


def parse_cpu_power_from_hsmp(socket_count: int = 2):
    result = {"cpu_curr_pwr_0": None, "cpu_curr_pwr_1": None}

    if not os.path.exists(HSMP_DEV):
        return result

    for idx in range(min(socket_count, 2)):
        try:
            mw = read_hsmp_socket_power_mw(idx)
        except Exception:
            # ENODEV on a single-socket board when probing socket 1; the key
            # stays None rather than reporting a phantom second socket.
            continue
        if mw:
            result[f"cpu_curr_pwr_{idx}"] = round(mw / 1000.0, 1)

    return result


# Latched so the "no CPU power source" warning is logged on state change only:
# this runs ~1x/sec and both probes fail silently by design.
_cpu_power_unavailable = False


def get_cpu_power_telemetry(sensors_data):
    global _cpu_power_unavailable

    result = {"cpu_curr_pwr_0": None, "cpu_curr_pwr_1": None}

    try:
        ipmi = get_ipmi_power_output()
        if ipmi.stdout:
            result = parse_cpu_power_telemetry(ipmi.stdout)
    except Exception:
        pass

    if all(v is None for v in result.values()):
        try:
            result = parse_cpu_power_from_sensors(sensors_data)
        except Exception:
            result = {"cpu_curr_pwr_0": None, "cpu_curr_pwr_1": None}

    if all(v is None for v in result.values()):
        try:
            result = parse_cpu_power_from_hsmp()
        except Exception:
            result = {"cpu_curr_pwr_0": None, "cpu_curr_pwr_1": None}

    unavailable = all(v is None for v in result.values())
    if unavailable != _cpu_power_unavailable:
        if unavailable:
            print(
                "[WARN] CPU power unavailable: no POWER_CPU/POWER_CPU1/POWER_CPU2 "
                "IPMI sensor, no hwmon power*_input reading, and no HSMP "
                "(/dev/hsmp) response",
                flush=True,
            )
        else:
            print("[INFO] CPU power reading recovered", flush=True)
        _cpu_power_unavailable = unavailable

    return result


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
    # No mst device means no Mellanox card, so skip the probe entirely. On such
    # hosts `sudo mget_temp` can still outlast its timeout, and the resulting
    # TimeoutExpired escapes write_metrics_once() before pipe.execute() runs --
    # discarding that cycle's GPU, CPU, NVMe and memory metrics along with it.
    if not os.path.exists(mst_dev):
        return None

    try:
        p = subprocess.run(
            ["sudo", "-n", "mget_temp", "-d", mst_dev],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None

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
    curr_npusinfo = get_furiosa_npu_telemetry()
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
        pipe.set(f"gpu_name_{idx}", str(gpu[0]), ex=CHIP_KEY_TTL_SEC)
        pipe.set(f"gpu_temp_{idx}", str(gpu[1]), ex=CHIP_KEY_TTL_SEC)
        pipe.set(f"gpu_curr_pwr_{idx}", str(gpu[2]), ex=CHIP_KEY_TTL_SEC)
        pipe.set(f"gpu_max_pwr_{idx}", str(gpu[3]), ex=CHIP_KEY_TTL_SEC)
        pipe.set(f"gpu_curr_mem_{idx}", str(gpu[4]), ex=CHIP_KEY_TTL_SEC)
        pipe.set(f"gpu_max_mem_{idx}", str(gpu[5]), ex=CHIP_KEY_TTL_SEC)

    # NPU (furiosa-smi reports no power limit, so npu_max_pwr_* is never set)
    for idx, npu in curr_npusinfo.items():
        pipe.set(f"npu_name_{idx}", npu["name"], ex=CHIP_KEY_TTL_SEC)
        pipe.set(f"npu_temp_{idx}", str(npu["temp"]), ex=CHIP_KEY_TTL_SEC)
        if npu["power"] is not None:
            pipe.set(f"npu_curr_pwr_{idx}", str(npu["power"]), ex=CHIP_KEY_TTL_SEC)
        if "mem_total" in npu:
            pipe.set(f"npu_curr_mem_{idx}", str(npu["mem_used"]), ex=CHIP_KEY_TTL_SEC)
            pipe.set(f"npu_max_mem_{idx}", str(npu["mem_total"]), ex=CHIP_KEY_TTL_SEC)

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