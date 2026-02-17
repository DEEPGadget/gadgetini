#!/usr/bin/env python3
"""
fake_exporter_dg5R.py
Generates fake sensor data matching sensor_exporter_dg5R.py metric format.
Runs on port 9003 for Prometheus scraping.
"""
import time
import random
import math
from prometheus_client import start_http_server, CollectorRegistry
from prometheus_client.core import GaugeMetricFamily

# Simulate slowly drifting values with noise
class Sim:
    def __init__(self, base, drift=0.5, noise=0.3):
        self.base = base
        self.drift = drift
        self.noise = noise
        self.t = 0

    def val(self):
        self.t += 1
        wave = math.sin(self.t * 0.02) * self.drift
        n = random.gauss(0, self.noise)
        return round(self.base + wave + n, 2)

# --- Simulated values ---
# Coolant
sim_inlet1  = Sim(28.0, drift=2.0, noise=0.3)
sim_inlet2  = Sim(27.5, drift=2.0, noise=0.3)
sim_outlet1 = Sim(42.0, drift=3.0, noise=0.5)
sim_outlet2 = Sim(41.5, drift=3.0, noise=0.5)

# Chassis
sim_air_temp  = Sim(32.0, drift=2.0, noise=0.5)
sim_air_humid = Sim(45.0, drift=5.0, noise=1.0)

# GPU (8 GPUs)
NUM_GPUS = 8
sim_gpu_temp  = [Sim(65.0 + i*0.5, drift=5.0, noise=1.0) for i in range(NUM_GPUS)]
sim_gpu_power = [Sim(350.0 + i*5, drift=20.0, noise=5.0) for i in range(NUM_GPUS)]
sim_gpu_core  = [Sim(60.0, drift=15.0, noise=3.0) for i in range(NUM_GPUS)]
sim_gpu_mem   = [Sim(55.0, drift=10.0, noise=2.0) for i in range(NUM_GPUS)]

# CPU (2 CPUs)
sim_cpu_temp  = [Sim(55.0, drift=5.0, noise=1.0), Sim(54.0, drift=5.0, noise=1.0)]
sim_cpu_power = [Sim(120.0, drift=15.0, noise=3.0), Sim(118.0, drift=15.0, noise=3.0)]
sim_cpu_util  = Sim(35.0, drift=15.0, noise=3.0)

# Memory
sim_mem_total = 512.0  # fixed
sim_mem_used  = Sim(280.0, drift=30.0, noise=5.0)
sim_swap_used = Sim(0.2, drift=0.3, noise=0.1)

# Network
sim_net_tx = Sim(2.5, drift=1.0, noise=0.2)
sim_net_rx = Sim(3.0, drift=1.5, noise=0.3)
sim_net_err = Sim(0.002, drift=0.001, noise=0.0005)
sim_net_drop = Sim(0.005, drift=0.003, noise=0.001)


class FakeDg5RCollector:
    def collect(self):
        g = GaugeMetricFamily(
            "DLC_sensors_gauge",
            "deepgadget DLC sensors telemetry",
            labels=['server_name', 'metric', 'description']
        )

        # ── Cooling ──
        inlet1 = sim_inlet1.val()
        inlet2 = sim_inlet2.val()
        outlet1 = sim_outlet1.val()
        outlet2 = sim_outlet2.val()
        delta1 = round(outlet1 - inlet1, 2)
        delta2 = round(outlet2 - inlet2, 2)

        g.add_metric(["dg5R", "Coolant temperature inlet1", "degree celcious"], inlet1)
        g.add_metric(["dg5R", "Coolant temperature outlet1", "degree celcious"], outlet1)
        g.add_metric(["dg5R", "Coolant deltaT1", "degree celcious"], delta1)
        g.add_metric(["dg5R", "Coolant temperature inlet2", "degree celcious"], inlet2)
        g.add_metric(["dg5R", "Coolant temperature outlet2", "degree celcious"], outlet2)
        g.add_metric(["dg5R", "Coolant deltaT2", "degree celcious"], delta2)

        # Leak: 0 = normal, 1 = leaked (keep normal most of the time)
        g.add_metric(["dg5R", "LEAK detection", "if leak: value = 1"],
                      1 if random.random() < 0.02 else 0)
        # Level: 1 = full, 0 = low
        g.add_metric(["dg5R", "Coolant level", "if full: value = 1"],
                      0 if random.random() < 0.03 else 1)

        # ── Chassis ──
        g.add_metric(["dg5R", "Air temperature", "degree celcious"], sim_air_temp.val())
        g.add_metric(["dg5R", "Air humidity", "%"], max(0, sim_air_humid.val()))

        # ── GPU ──
        for i in range(NUM_GPUS):
            label = f"H100_NVL_{i}"
            g.add_metric(["dg5R", f"{label} asic temperature", "degree celcious"],
                          sim_gpu_temp[i].val())
            g.add_metric(["dg5R", f"{label} current power usage", "W"],
                          max(0, sim_gpu_power[i].val()))
            g.add_metric(["dg5R", f"{label} Max power limit", "W"], 700.0)
            g.add_metric(["dg5R", f"{label} core utilization", "%"],
                          max(0, min(100, sim_gpu_core[i].val())))
            g.add_metric(["dg5R", f"{label} memory utilization", "%"],
                          max(0, min(100, sim_gpu_mem[i].val())))

        # ── CPU ──
        for i in range(2):
            g.add_metric(["dg5R", f"CPU{i} temperature", "degree celcious"],
                          sim_cpu_temp[i].val())
            g.add_metric(["dg5R", f"CPU{i} power usage", "W"],
                          max(0, sim_cpu_power[i].val()))
        g.add_metric(["dg5R", "CPU Usage", "%"],
                      max(0, min(100, sim_cpu_util.val())))

        # ── Memory ──
        used = max(0, sim_mem_used.val())
        avail = max(0, sim_mem_total - used)
        g.add_metric(["dg5R", "Memory_total", "GB"], sim_mem_total)
        g.add_metric(["dg5R", "Memory_usage", "GB"], used)
        g.add_metric(["dg5R", "Memory_available", "GB"], avail)
        g.add_metric(["dg5R", "Swap_usage", "GB"], max(0, sim_swap_used.val()))
        g.add_metric(["dg5R", "OOM_count", "count"], 1 if random.random() < 0.05 else 0)

        # ── Network ──
        g.add_metric(["dg5R", "Network link status", "1=UP 0=DOWN"],
                      0 if random.random() < 0.02 else 1)
        g.add_metric(["dg5R", "Network TX throughput", "Gbps"],
                      max(0, sim_net_tx.val()))
        g.add_metric(["dg5R", "Network RX throughput", "Gbps"],
                      max(0, sim_net_rx.val()))
        g.add_metric(["dg5R", "Network errors rate", "%"],
                      max(0, sim_net_err.val()))
        g.add_metric(["dg5R", "Network drops rate", "%"],
                      max(0, sim_net_drop.val()))

        yield g


if __name__ == "__main__":
    port = 9003
    registry = CollectorRegistry()
    registry.register(FakeDg5RCollector())
    start_http_server(port, registry=registry)
    print(f"Fake dg5R exporter running on :{port}")
    while True:
        time.sleep(2)
