from sensor_data import SensorData
from viewer import SensorViewer

GPU_COUNT = 8


def create_sensors(redis):
    r = redis
    return {
        # Dual coolant loops
        "coolant_inlet1": SensorData(
            "Coolant Inlet1", "\u00b0C", 15, 50,
            read_rate=1, redis=r, redis_key='coolant_temp_inlet1'),
        "coolant_outlet1": SensorData(
            "Coolant Outlet1", "\u00b0C", 15, 60,
            read_rate=1, redis=r, redis_key='coolant_temp_outlet1'),
        "coolant_delta1": SensorData(
            "Coolant \u0394T1", "\u00b0C", 0, 20,
            read_rate=1, redis=r, redis_key='coolant_delta_t1'),
        "coolant_inlet2": SensorData(
            "Coolant Inlet2", "\u00b0C", 15, 50,
            read_rate=1, redis=r, redis_key='coolant_temp_inlet2'),
        "coolant_outlet2": SensorData(
            "Coolant Outlet2", "\u00b0C", 15, 60,
            read_rate=1, redis=r, redis_key='coolant_temp_outlet2'),
        "coolant_delta2": SensorData(
            "Coolant \u0394T2", "\u00b0C", 0, 20,
            read_rate=1, redis=r, redis_key='coolant_delta_t2'),
        # Air
        "chassis_temp": SensorData(
            "Air Temperature", "\u00b0C", -20, 60,
            read_rate=1, redis=r, redis_key='air_temp'),
        "chassis_humid": SensorData(
            "Chassis Humidity", "%", 0, 100,
            read_rate=1, redis=r, redis_key='air_humit'),
        # GPU
        "xpu_temp": SensorData(
            "Max GPU Temperature", "\u00b0C", 10, 120,
            read_rate=1, redis=r,
            redis_keys=[f"gpu{i}_gpu_temp" for i in range(GPU_COUNT)]),
        "xpu_power": SensorData(
            "Max GPU Power", "W", 0, 700,
            read_rate=1, redis=r,
            redis_keys=[f"gpu{i}_gpu_power" for i in range(GPU_COUNT)]),
        # CPU
        "cpu_temp": SensorData(
            "Max CPU Temperature", "\u00b0C", 10, 120,
            read_rate=1, redis=r,
            redis_keys=["cpu_0_temp", "cpu_1_temp"]),
        "cpu_util": SensorData(
            "CPU Utilization", "%", 0, 100,
            read_rate=1, redis=r, redis_key='cpu_util'),
        # Memory
        "mem_util": SensorData(
            "Memory Utilization", "%", 0, 100,
            read_rate=1, redis=r,
            formula=lambda r: float(r.get('used_mem')) / float(r.get('total_mem')) * 100),
        "mem_used": SensorData(
            "Used Memory", "GB", 0, 2048,
            read_rate=1, redis=r, redis_key='used_mem'),
        "mem_free": SensorData(
            "Free Memory", "GB", 0, 2048,
            read_rate=1, redis=r, redis_key='avail_mem'),
    }


def create_viewers():
    return [
        SensorViewer("Coolant Loop1",
                     sensor_key="coolant_inlet1",
                     sub1_key="coolant_outlet1",
                     sub2_key="coolant_delta1"),
        SensorViewer("Coolant Loop2",
                     sensor_key="coolant_inlet2",
                     sub1_key="coolant_outlet2",
                     sub2_key="coolant_delta2"),
        SensorViewer("GPU Info",
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
        "coolant_inlet1": SensorData(
            "Coolant Inlet1", "\u00b0C", 15, 50,
            read_rate=1, redis=r, redis_key='coolant_temp_inlet1'),
        "coolant_outlet1": SensorData(
            "Coolant Outlet1", "\u00b0C", 15, 60,
            read_rate=1, redis=r, redis_key='coolant_temp_outlet1'),
        "coolant_delta1": SensorData(
            "Coolant \u0394T1", "\u00b0C", 0, 20,
            read_rate=1, redis=r, redis_key='coolant_delta_t1'),
        "chassis_temp": SensorData(
            "Air Temperature", "\u00b0C", -20, 60,
            read_rate=1, redis=r, redis_key='air_temp'),
        "chassis_humid": SensorData(
            "Chassis Humidity", "%", 0, 100,
            read_rate=1, redis=r, redis_key='air_humit'),
    }


def create_fallback_viewers():
    return [
        SensorViewer("Coolant Loop1",
                     sensor_key="coolant_inlet1",
                     sub1_key="coolant_outlet1",
                     sub2_key="coolant_delta1"),
    ]
