import redis
import dlc_sensors

rd = redis.StrictRedis(host='localhost', port=6379, db=0)


'''
         Key       : Value
--------------------------------         
    cpu_temp       : float
    cpu_util       : float
    n300_temp      : float
    gpu_temp       : float
    coolant_temp   : float
    coolant_leak   : bool
    coolant_level  : bool
    air_temp       : float 
    air_humit      : float
    chassis_stabil : bool 
'''

while True:
    rd.set("coolant_temp", get_coolant_temp()) 
    rd.set("coolant_leak", get_coolant_leak_detection())
    rd.set("coolant_level", get_coolant_level_detection())
    rd.set("air_temp", get_air_temp())
    rd.set("air_humit", get_air_humit())
    rd.set("chassis_stabil", get_chassis_stabil())
    
