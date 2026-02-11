import redis
import dlc_sensors

rd = redis.StrictRedis(host='localhost', port=6379, db=0)


'''
         Key                 : Value
--------------------------------------------
    cpu_temp                 : float
    cpu_util                 : float
    n300_temp                : float
    gpu_temp                 : float
    coolant_temp_ad2         : float
    coolant_temp_ad3         : float
    coolant_temp_ad4         : float
    coolant_temp_ad5         : float
    coolant_leak             : bool
    coolant_level            : bool
    air_temp                 : float
    air_humit                : float
'''

while True:

    rd.set("coolant_temp_ad2", dlc_sensors.get_coolant_temp(2))
    rd.set("coolant_temp_ad3", dlc_sensors.get_coolant_temp(3))
    rd.set("coolant_temp_ad4", dlc_sensors.get_coolant_temp(4))
    rd.set("coolant_temp_ad5", dlc_sensors.get_coolant_temp(5))

    rd.set("coolant_leak", dlc_sensors.get_coolant_leak_detection())
    rd.set("coolant_level", dlc_sensors.get_coolant_level_detection())
    rd.set("air_temp", dlc_sensors.get_air_temp())
    rd.set("air_humit", dlc_sensors.get_air_humit())

