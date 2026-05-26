#!/usr/bin/python3
# -*- coding: utf-8 -*-
import redis
import dlc_sensors
import time
from machine_config import MACHINE, COOLANT_CHANNELS

rd = redis.StrictRedis(host='localhost', port=6379, db=0)


# data_crawler_host.py refreshes `host_ttl` (ms timestamp) every cycle with
# EXPIRE 7. We treat the key's presence as proof that host telemetry is
# actually arriving — this works whether the host reaches us over the USB
# gadget link or via an external router, and it also catches host-side
# script crashes that a pure link check would miss.
HOST_TTL_KEY = 'host_ttl'


def is_host_alive(*_args, **_kwargs) -> int:
    """1 if the host's heartbeat key is still present in Redis, else 0."""
    try:
        return 1 if rd.exists(HOST_TTL_KEY) else 0
    except redis.RedisError:
        return 0


while True:
    adc = dlc_sensors._collect_adc_samples()
    channels = COOLANT_CHANNELS.get(MACHINE, {})

    pipe = rd.pipeline(transaction=False)

    temps = {}
    for name, idx in channels.items():
        temp = dlc_sensors.get_coolant_temp(idx, adc)
        temps[name] = temp
        key = f"coolant_temp_{name}"
        if temp is None:
            pipe.delete(key)
        else:
            pipe.set(key, temp)

    # compute delta_t only when both inlet and outlet of the pair are present this cycle
    def _delta_or_clear(in_name, out_name, key):
        i, o = temps.get(in_name), temps.get(out_name)
        if i is not None and o is not None:
            pipe.set(key, round(o - i, 2))
        else:
            pipe.delete(key)

    _delta_or_clear('inlet1', 'outlet1', 'coolant_delta_t1')
    _delta_or_clear('inlet2', 'outlet2', 'coolant_delta_t2')

    pipe.set("coolant_leak",  dlc_sensors.get_coolant_leak_detection(adc))
    pipe.set("coolant_level", dlc_sensors.get_coolant_level_detection(adc))
    pipe.set("air_temp",      dlc_sensors.get_air_temp())
    pipe.set("air_humit",     dlc_sensors.get_air_humit())
    pipe.set("host_stat",     str(is_host_alive()))

    stabil = dlc_sensors.get_chassis_stabil()
    if stabil is not None:
        pipe.set("chassis_stabil", stabil)

    pipe.execute()
    time.sleep(1)
