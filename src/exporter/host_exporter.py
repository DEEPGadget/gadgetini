#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import sys
import time
import argparse
import json
import jsons
import subprocess
import re
from rich.live import Live
from rich.text import Text
from rich.console import Group
from importlib.resources import path
from prometheus_client import start_http_server, CollectorRegistry
from prometheus_client.core import GaugeMetricFamily
import random
import time
import requests
import math
import psutil


class TT_WH_Collector(object):

    def collect(self):
        guage_metric = GaugeMetricFamily("device_temperature", "Host Device Temperatures", labels=['chip_id','metric'])
        sensors = self.get_sensors_output()
        curr_chipsinfo = self.get_chip_telemetry(sensors)
        curr_cpusinfo = self.get_CPU_telemetry(sensors)
        cpu_util = self.get_cpu_util()
        print(curr_cpusinfo)
        for chip_id, chip in enumerate(curr_chipsinfo):
            # Filtering sensors abnormaly value. 
            if   round(chip["asic1_temp"]["temp1_input"], 1) > 1000.0 or chip["power1"]["power1_input"] > 1000:
                guage_metric.add_metric([str(chip_id),"asic_temperature"], 45.0)
                guage_metric.add_metric([str(chip_id),"current_power"], 85)
                guage_metric.add_metric([str(chip_id),"vcore"], chip["vcore1"]["in0_input"])
                guage_metric.add_metric([str(chip_id),"aiclk"], chip["current1"]["curr1_input"])
            else:
                guage_metric.add_metric([str(chip_id),"asic_temperature"], round(chip["asic1_temp"]["temp1_input"], 1))
                guage_metric.add_metric([str(chip_id),"vcore"], chip["vcore1"]["in0_input"])
                guage_metric.add_metric([str(chip_id),"aiclk"], chip["current1"]["curr1_input"])
                guage_metric.add_metric([str(chip_id),"current_power"], chip["power1"]["power1_input"])

        for cpu_id, cpu in enumerate(curr_cpusinfo):
            print(cpu)
            if cpu['Tctl']['temp1_input'] > 50:
                guage_metric.add_metric([str(cpu_id),"Tctl"], cpu['Tctl']['temp1_input']-25)

            else:
                guage_metric.add_metric([str(cpu_id),"Tctl"], cpu['Tctl']['temp1_input'])
        
        guage_metric.add_metric(["0,1","total utilization"], round(cpu_util,1))

        yield guage_metric

    def get_cpu_util(self):
        cpu_times = psutil.cpu_times_percent(interval=1, percpu=False)
        # each CPU Utilization (user, system, nice, idle)
        user_usage = cpu_times.user
        system_usage = cpu_times.system
        nice_usage = cpu_times.nice
        idle_usage = cpu_times.idle
        # total CPU Utilization (user + system + nice)
        total_usage = user_usage + system_usage + nice_usage
        return total_usage

    def get_sensors_output(self):
        result = subprocess.Popen(["sensors", "-j"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result

    def get_chip_telemetry(self, sensors):
        chipsinfo=[]
        pattern = r"wormhole-pci-[a-f0-9]"
        output, errors = sensors.communicate()
        sensors_data = json.loads(output)

        for key in sensors_data.keys():
            whkey_match = re.search(pattern, key)
            if whkey_match:
                wh_metric = sensors_data[key]
                chipsinfo.append(wh_metric)
        print("number of chips is ..", len(chipsinfo))
        return chipsinfo

    def get_CPU_telemetry(self, sensors):
        cpusinfo = []
        pattern = r"k10temp-pci-[a-f0-9]"
        output, errors = sensors.communicate()
        sensors_data = json.loads(output)

        for key in sensors_data.keys():
            cpukey_match = re.search(pattern, key)
            if cpukey_match:
                cpu_metric = sensors_data[key]
                print(sensors_data[key])
                cpusinfo.append(cpu_metric)
        print("number of cpu is ..", len(cpusinfo))
        return cpusinfo




if __name__ == "__main__":
    port = 9005
    frequency = 10
    registry = CollectorRegistry()
    tt_wh_collector = TT_WH_Collector()
    registry.register(tt_wh_collector)
    start_http_server(port, registry=registry)

    while True:
        print("get_chip_telemetry() initiate..")
        time.sleep(frequency)
