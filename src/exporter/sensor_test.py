#!/usr/bin/python
# -*- coding:utf-8 -*-
import sensing_interface_for_display as sensor
import redis



rd = redis.StrictRedis(host='localhost', port=6379, db=0)


while True:
    rd.set("coolant_temp",sensor.get_coolant_temp())
    rd.get("coolant_temp")
    rd.set("humit",sensor.get_air_humit())
    rd.get("humit")
    rd.set("temp",sensor.get_air_temp())
    rd.get("temp")
