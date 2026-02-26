#!/usr/bin/python3
# -*- coding: utf-8 -*-
import redis
import dlc_sensors
import time
from config import MACHINE, COOLANT_CHANNELS

rd = redis.StrictRedis(host='localhost', port=6379, db=0)


def is_host_alive(key: str, dead_after_sec: float = 5.0) -> int:
    ttl_ms = rd.pttl(key)
    return 1 if ttl_ms > 0 else 0


while True:
    adc = dlc_sensors._collect_adc_samples()
    channels = COOLANT_CHANNELS.get(MACHINE, {})

    pipe = rd.pipeline(transaction=False)

    temps = {}
    for name, idx in channels.items():
        temp = dlc_sensors.get_coolant_temp(idx, adc)
        temps[name] = temp
        pipe.set(f"coolant_temp_{name}", temp)

    # compute delta_t only when inlet+outlet pair exists (dg5w has inlet1 only for now, skip)
    if 'inlet1' in temps and 'outlet1' in temps:
        pipe.set("coolant_delta_t1", round(temps['outlet1'] - temps['inlet1'], 2))
    if 'inlet2' in temps and 'outlet2' in temps:
        pipe.set("coolant_delta_t2", round(temps['outlet2'] - temps['inlet2'], 2))

    pipe.set("coolant_leak",  dlc_sensors.get_coolant_leak_detection(adc))
    pipe.set("coolant_level", dlc_sensors.get_coolant_level_detection(adc))
    pipe.set("air_temp",      dlc_sensors.get_air_temp())
    pipe.set("air_humit",     dlc_sensors.get_air_humit())
    pipe.set("host_stat",     str(is_host_alive("host_ttl", 5.0)))

    stabil = dlc_sensors.get_chassis_stabil()
    if stabil is not None:
        pipe.set("chassis_stabil", stabil)

    pipe.execute()
    time.sleep(1)
