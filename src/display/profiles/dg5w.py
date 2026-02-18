from sensor_data import SensorData
from viewer import SensorViewer

def create_sensors(redis, config=None):
    r = redis
    gpu_count = config.getint('PRODUCT', 'gpu_count', fallback=8) if config else 8
    return {
        "coolant_temp": SensorData(
            "Coolant Temperature", "\u00b0C", 25, 50,
            read_rate=1, redis=r, redis_key='coolant_temp',
            icon="\U000f0510"),
        "chassis_temp": SensorData(
            "Chassis Temperature", "\u00b0C", -20, 60,
            read_rate=1, redis=r, redis_key='air_temp',
            icon="\U000f0510"),
        "chassis_humid": SensorData(
            "Chassis Humidity", "%", 0, 100,
            read_rate=1, redis=r, redis_key='air_humit',
            icon="\U000f058e"),
        "xpu_temp": SensorData(
            "Max GPU Temperature", "\u00b0C", 10, 120,
            read_rate=1, redis=r,
            redis_keys=[f"gpu_temp_{i}" for i in range(gpu_count)],
            icon="\U000f0510"),
        "xpu_power": SensorData(
            "Max GPU Power", "W", 0, 600,
            read_rate=1, redis=r,
            redis_keys=[f"gpu_curr_pwr_{i}" for i in range(gpu_count)],
            icon="\U000f140b"),
        "cpu_temp": SensorData(
            "Max CPU Temperature", "\u00b0C", 10, 120,
            read_rate=1, redis=r,
            redis_keys=["cpu_temp_0", "cpu_temp_1"],
            icon="\U000f0510"),
        "cpu_util": SensorData(
            "CPU Utilization", "%", 0, 100,
            read_rate=1, redis=r, redis_key='cpu_usage',
            icon="\U000f0ee0"),
        "mem_util": SensorData(
            "Memory Utilization", "%", 0, 100,
            read_rate=1, redis=r,
            formula=lambda r: float(r.get('mem_usage')) / float(r.get('mem_total')) * 100,
            icon="\U000f035b"),
        "mem_used": SensorData(
            "Used Memory", "GB", 0, 1024,
            read_rate=1, redis=r, redis_key='mem_usage',
            icon="\U000f035b"),
        "mem_free": SensorData(
            "Free Memory", "GB", 0, 1024,
            read_rate=1, redis=r, redis_key='mem_available',
            icon="\U000f035b"),
    }


def create_viewers(config=None):
    return [
        ("chassis", SensorViewer("Chassis Info",
                     sensor_key="coolant_temp",
                     sub1_key="chassis_temp",
                     sub2_key="chassis_humid")),
        ("gpu", SensorViewer("XPU Info",
                     sensor_key="xpu_temp",
                     sub1_key="xpu_power",
                     sub2_key="chassis_humid")),
        ("cpu", SensorViewer("CPU Info",
                     sensor_key="cpu_temp",
                     sub1_key="cpu_util",
                     sub2_key="chassis_humid",
                     sub1_autoscale=True)),
        ("memory", SensorViewer("MEM Info",
                     sensor_key="mem_util",
                     sub1_key="mem_used",
                     sub2_key="mem_free",
                     fixed_min=0, fixed_max=100,
                     sub1_autoscale=True,
                     sub2_autoscale=True)),
    ]


def create_fallback_sensors(redis):
    r = redis
    return {
        "coolant_temp": SensorData(
            "Coolant Temperature", "\u00b0C", 25, 50,
            read_rate=1, redis=r, redis_key='coolant_temp',
            icon="\U000f0510"),
        "chassis_temp": SensorData(
            "Chassis Temperature", "\u00b0C", -20, 60,
            read_rate=1, redis=r, redis_key='air_temp',
            icon="\U000f0510"),
        "chassis_humid": SensorData(
            "Chassis Humidity", "%", 0, 100,
            read_rate=1, redis=r, redis_key='air_humit',
            icon="\U000f058e"),
    }


def create_fallback_viewers():
    return [
        ("chassis", SensorViewer("Chassis Info",
                     sensor_key="coolant_temp",
                     sub1_key="chassis_temp",
                     sub2_key="chassis_humid")),
    ]
