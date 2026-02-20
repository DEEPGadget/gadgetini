import redis
import dlc_sensors_dg5R as dlc_sensors

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

while True:
    inlet1  = dlc_sensors.get_coolant_temp(2)
    outlet1 = dlc_sensors.get_coolant_temp(3)

    outlet2 = dlc_sensors.get_coolant_temp(4)
    inlet2  = dlc_sensors.get_coolant_temp(5)

    delta_t1 = round(outlet1 - inlet1, 2)
    delta_t2 = round(outlet2 - inlet2, 2)

    rd.set("coolant_temp_inlet1", inlet1)
    rd.set("coolant_temp_outlet1", outlet1)
    rd.set("coolant_delta_t1", delta_t1)

    rd.set("coolant_temp_inlet2", inlet2)
    rd.set("coolant_temp_outlet2", outlet2)
    rd.set("coolant_delta_t2", delta_t2)

    rd.set("coolant_leak",  dlc_sensors.get_coolant_leak_detection())
    rd.set("coolant_level", dlc_sensors.get_coolant_level_detection())
    rd.set("air_temp",      dlc_sensors.get_air_temp())
    rd.set("air_humit",     dlc_sensors.get_air_humit())

