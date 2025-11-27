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
class TT_WH_Collector(object):

    def collect(self):
        guage_metric = GaugeMetricFamily("WH_device_guage", "Tenstorrent n300 WormHole telemetry", labels=['chip_id','metric'])
        curr_chipsinfo = self.get_chip_telemetry()

        for chip_id, chip in enumerate(curr_chipsinfo):
            # Filtering sensors abnormaly value. 
            if   round(chip["asic1_temp"]["temp1_input"], 1) > 1000.0 or chip["power1"]["power1_input"] > 1000:
                guage_metric.add_metric([str(chip_id),"asic_temperature"], 45.0)
                guage_metric.add_metric([str(chip_id),"current_power"], 85)
            else:
                guage_metric.add_metric([str(chip_id),"asic_temperature"], round(chip["asic1_temp"]["temp1_input"], 1))
                guage_metric.add_metric([str(chip_id),"vcore"], chip["vcore1"]["in0_input"])
                guage_metric.add_metric([str(chip_id),"aiclk"], chip["current1"]["curr1_input"])
                guage_metric.add_metric([str(chip_id),"current_power"], chip["power1"]["power1_input"] )

        yield guage_metric

    def get_chip_telemetry(self):
        chipsinfo=[]
        pattern = r"wormhole-pci-[a-f0-9]"
        sensors = subprocess.Popen(["sensors", "-j"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output, errors = sensors.communicate()
        sensors_data = json.loads(output)

        for key in sensors_data.keys():
            whkey_match = re.search(pattern, key)
            if whkey_match:
                wh_metric = sensors_data[key]
                chipsinfo.append(wh_metric)
        print("number of chips is ..", len(chipsinfo))
        return chipsinfo




if __name__ == "__main__":
    port = 9000
    frequency = 10
    registry = CollectorRegistry()
    tt_wh_collector = TT_WH_Collector()
    registry.register(tt_wh_collector)
    start_http_server(port, registry=registry)

    while True:
        print("get_chip_telemetry() initiate..")
        time.sleep(frequency)