import redis
import dlc_sensors_dg5R as dlc_sensors
from typing import Any
import time
rd = redis.StrictRedis(host='localhost', port=6379, db=0)

'''
         Key                      : Value
-------------------------------------------------------
    coolant_temp_inlet1           : float
    coolant_temp_outlet1          : float
    coolant_delta_t1              : float

    coolant_temp_inlet2           : float
    coolant_temp_outlet2          : float
    coolant_delta_t2              : float

    coolant_leak                  : bool
    coolant_level                 : bool

    air_temp                      : float
    air_humit                     : float
'''
def is_host_alive(rd, key: str, dead_after_sec: float = 5.0) -> int:
  ttl_ms = rd.pttl(key)
  return 1 if ttl_ms > 0 else 0
  

while True:
    inlet1  = dlc_sensors.get_coolant_temp(2)
    outlet1 = dlc_sensors.get_coolant_temp(3)

    outlet2 = dlc_sensors.get_coolant_temp(4)
    inlet2  = dlc_sensors.get_coolant_temp(5)

    delta_t1 = round(outlet1 - inlet1, 2)
    delta_t2 = round(outlet2 - inlet2, 2)
    
    pipe = rd.pipeline(transaction=False)
    
    pipe.set("coolant_temp_inlet1", inlet1)
    pipe.set("coolant_temp_outlet1", outlet1)
    pipe.set("coolant_delta_t1", delta_t1)

    pipe.set("coolant_temp_inlet2", inlet2)
    pipe.set("coolant_temp_outlet2", outlet2)
    pipe.set("coolant_delta_t2", delta_t2)

    pipe.set("coolant_leak",  dlc_sensors.get_coolant_leak_detection())
    pipe.set("coolant_level", dlc_sensors.get_coolant_level_detection())
    pipe.set("air_temp",      dlc_sensors.get_air_temp())
    pipe.set("air_humit",     dlc_sensors.get_air_humit())
    pipe.set("host_stat", str(is_host_alive(rd, "host_ttl", 5.0)))
    pipe.execute()
    time.sleep(1)

