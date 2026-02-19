import redis
import dlc_sensors_dg5R as dlc_sensors
import subprocess
from typing import Optional
import time

rd = redis.StrictRedis(host='localhost', port=6379, db=0)

'''
         Key                      : Value
-------------------------------------------------------
    cpu_temp                      : float
    cpu_util                      : float
    n300_temp                     : float
    gpu_temp                      : float

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

def is_host_alive(addr: str = "fd12:3456:789a:1::2",
                         attempts: int = 5,
                         timeout_sec: int = 1,
                         interface: Optional[str] = None) -> int:
    """
    Return 1 if the server is considered alive (any ping succeeds within attempts),
    else return 0 after `attempts` consecutive failures.

    - Linux ping used: ping -6 -c 1 -W <timeout> <addr>
    - attempts=5 means: if 5 tries all fail => 0 (dead). If any succeeds => 1 (alive).

    Args:
        addr: Target IPv6 address to ping.
        attempts: Number of attempts before declaring dead.
        timeout_sec: Per-attempt timeout in seconds.
        interface: Optional outgoing interface name (e.g., "usb0"). If set, uses `-I`.

    Returns:
        1 if alive, 0 if dead.
    """
    cmd_base = ["ping", "-6", "-c", "1", "-W", str(int(timeout_sec))]
    if interface:
        cmd_base += ["-I", interface]

    for _ in range(max(1, attempts)):
        p = subprocess.run(cmd_base + [addr],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        if p.returncode == 0:
            return str(1)
    return str(0)


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
#    rd.set("host_stat", "0")
    rd.set("host_stat", is_host_alive())
    time.sleep(2)

