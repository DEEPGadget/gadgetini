from sensor_data import SensorData
from viewer import SensorViewer

GPU_COUNT = 8


def create_sensors(redis):
    r = redis
    return {
        "coolant_temp": SensorData(
            "Coolant Temperature", "\u00b0C", 25, 50,
            read_rate=1, redis=r, redis_key='coolant_temp'),
        "chassis_temp": SensorData(
            "Chassis Temperature", "\u00b0C", -20, 60,
            read_rate=1, redis=r, redis_key='air_temp'),
        "chassis_humid": SensorData(
            "Chassis Humidity", "%", 0, 100,
            read_rate=1, redis=r, redis_key='air_humit'),
        "xpu_temp": SensorData(
            "Max GPU Temperature", "\u00b0C", 10, 120,
            read_rate=1, redis=r,
            redis_keys=[f"gpu_temp_{i}" for i in range(GPU_COUNT)]),
        "xpu_power": SensorData(
            "Max GPU Power", "W", 0, 600,
            read_rate=1, redis=r,
            redis_keys=[f"gpu_curr_pwr_{i}" for i in range(GPU_COUNT)]),
        "cpu_temp": SensorData(
            "Max CPU Temperature", "\u00b0C", 10, 120,
            read_rate=1, redis=r,
            redis_keys=["cpu_temp_0", "cpu_temp_1"]),
        "cpu_util": SensorData(
            "CPU Utilization", "%", 0, 100,
            read_rate=1, redis=r, redis_key='cpu_usage'),
        "mem_util": SensorData(
            "Memory Utilization", "%", 0, 100,
            read_rate=1, redis=r,
            formula=lambda r: float(r.get('mem_usage')) / float(r.get('mem_total')) * 100),
        "mem_used": SensorData(
            "Used Memory", "GB", 0, 1024,
            read_rate=1, redis=r, redis_key='mem_usage'),
        "mem_free": SensorData(
            "Free Memory", "GB", 0, 1024,
            read_rate=1, redis=r, redis_key='mem_available'),
    }


def create_viewers():
    return [
        SensorViewer("Chassis Info",
                     sensor_key="coolant_temp",
                     sub1_key="chassis_temp",
                     sub2_key="chassis_humid"),
        SensorViewer("XPU Info",
                     sensor_key="xpu_temp",
                     sub1_key="xpu_power",
                     sub2_key="chassis_humid"),
        SensorViewer("CPU Info",
                     sensor_key="cpu_temp",
                     sub1_key="cpu_util",
                     sub2_key="chassis_humid",
                     sub1_autoscale=True),
        SensorViewer("MEM Info",
                     sensor_key="mem_util",
                     sub1_key="mem_used",
                     sub2_key="mem_free",
                     fixed_min=0, fixed_max=100,
                     sub1_autoscale=True,
                     sub2_autoscale=True),
    ]


def create_fallback_sensors(redis):
    r = redis
    return {
        "coolant_temp": SensorData(
            "Coolant Temperature", "\u00b0C", 25, 50,
            read_rate=1, redis=r, redis_key='coolant_temp'),
        "chassis_temp": SensorData(
            "Chassis Temperature", "\u00b0C", -20, 60,
            read_rate=1, redis=r, redis_key='air_temp'),
        "chassis_humid": SensorData(
            "Chassis Humidity", "%", 0, 100,
            read_rate=1, redis=r, redis_key='air_humit'),
    }


def create_fallback_viewers():
    return [
        SensorViewer("Chassis Info",
                     sensor_key="coolant_temp",
                     sub1_key="chassis_temp",
                     sub2_key="chassis_humid"),
    ]
