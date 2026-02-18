from sensor_data import SensorData
from viewer import SensorViewer
from multi_viewer import MultiSensorViewer

GPU_COLORS = [
    (255, 60, 60),    # G0 Red
    (255, 160, 0),    # G1 Orange
    (255, 230, 0),    # G2 Yellow
    (0, 220, 100),    # G3 Green
    (0, 200, 255),    # G4 Cyan
    (60, 100, 255),   # G5 Blue
    (160, 80, 255),   # G6 Purple
    (255, 80, 200),   # G7 Pink
]

CPU_COLORS = [
    (0, 200, 255),    # CPU0 Cyan
    (255, 140, 0),    # CPU1 Orange
    (0, 220, 100),    # CPU2 Green
    (255, 60, 60),    # CPU3 Red
]


def create_sensors(redis, config=None):
    r = redis
    gpu_count = config.getint('PRODUCT', 'gpu_count', fallback=8) if config else 8
    cpu_count = config.getint('PRODUCT', 'cpu_count', fallback=2) if config else 2

    sensors = {
        # Dual coolant loops
        "coolant_inlet1": SensorData(
            "Coolant Inlet1", "\u00b0C", 15, 50,
            read_rate=1, redis=r, redis_key='coolant_temp_inlet1',
            icon="\U000f0510"),
        "coolant_outlet1": SensorData(
            "Coolant Outlet1", "\u00b0C", 15, 60,
            read_rate=1, redis=r, redis_key='coolant_temp_outlet1',
            icon="\U000f0510", label="OUT1"),
        "coolant_delta1": SensorData(
            "Coolant \u0394T1", "\u00b0C", 0, 20,
            read_rate=1, redis=r, redis_key='coolant_delta_t1',
            icon="\U000f0510", label="\u0394T1"),
        "coolant_inlet2": SensorData(
            "Coolant Inlet2", "\u00b0C", 15, 50,
            read_rate=1, redis=r, redis_key='coolant_temp_inlet2',
            icon="\U000f0510"),
        "coolant_outlet2": SensorData(
            "Coolant Outlet2", "\u00b0C", 15, 60,
            read_rate=1, redis=r, redis_key='coolant_temp_outlet2',
            icon="\U000f0510", label="OUT2"),
        "coolant_delta2": SensorData(
            "Coolant \u0394T2", "\u00b0C", 0, 20,
            read_rate=1, redis=r, redis_key='coolant_delta_t2',
            icon="\U000f0510", label="\u0394T2"),
        # Air
        "chassis_temp": SensorData(
            "Air Temperature", "\u00b0C", -20, 60,
            read_rate=1, redis=r, redis_key='air_temp',
            icon="\U000f0510"),
        "chassis_humid": SensorData(
            "Chassis Humidity", "%", 0, 100,
            read_rate=1, redis=r, redis_key='air_humit',
            icon="\U000f058e", label="HUM"),
        # GPU (individual temperatures)
        **{f"gpu{i}_temp": SensorData(
            f"GPU{i} Temp", "\u00b0C", 10, 120,
            read_rate=1, redis=r, redis_key=f'gpu{i}_gpu_temp',
            icon="\U000f0510", label=f"G{i}")
           for i in range(gpu_count)},
        "xpu_power": SensorData(
            "Max GPU Power", "W", 0, 700,
            read_rate=1, redis=r,
            redis_keys=[f"gpu{i}_gpu_power" for i in range(gpu_count)],
            icon="\U000f140b", label="PWR"),
        # CPU (individual temperatures)
        **{f"cpu{i}_temp": SensorData(
            f"CPU{i} Temperature", "\u00b0C", 10, 120,
            read_rate=1, redis=r, redis_key=f'cpu_{i}_temp',
            icon="\U000f0510", label=f"CPU{i}")
           for i in range(cpu_count)},
        "cpu_util": SensorData(
            "CPU Utilization", "%", 0, 100,
            read_rate=1, redis=r, redis_key='cpu_util',
            icon="\U000f0ee0", label="UTIL"),
        # Memory
        "mem_util": SensorData(
            "Memory Utilization", "%", 0, 100,
            read_rate=1, redis=r,
            formula=lambda r: float(r.get('used_mem')) / float(r.get('total_mem')) * 100,
            icon="\U000f035b"),
        "mem_used": SensorData(
            "Used Memory", "GB", 0, 2048,
            read_rate=1, redis=r, redis_key='used_mem',
            icon="\U000f035b", label="USED"),
        "mem_free": SensorData(
            "Free Memory", "GB", 0, 2048,
            read_rate=1, redis=r, redis_key='avail_mem',
            icon="\U000f035b", label="FREE"),
    }
    return sensors


def create_viewers(config=None):
    gpu_count = config.getint('PRODUCT', 'gpu_count', fallback=8) if config else 8
    cpu_count = config.getint('PRODUCT', 'cpu_count', fallback=2) if config else 2

    return [
        ("coolant", MultiSensorViewer(
            "Coolant Overview",
            sensor_keys=["coolant_inlet1", "coolant_outlet1",
                         "coolant_inlet2", "coolant_outlet2"],
            colors=[(0, 200, 255), (255, 140, 0),
                    (0, 220, 100), (255, 50, 200)],
            labels=["IN1", "OUT1", "IN2", "OUT2"])),
        ("chassis", SensorViewer("Coolant Loop1",
                     sensor_key="coolant_inlet1",
                     sub1_key="coolant_outlet1",
                     sub2_key="coolant_delta1")),
        ("chassis", SensorViewer("Coolant Loop2",
                     sensor_key="coolant_inlet2",
                     sub1_key="coolant_outlet2",
                     sub2_key="coolant_delta2")),
        ("gpu", MultiSensorViewer(
            "GPU Temperature",
            sensor_keys=[f"gpu{i}_temp" for i in range(gpu_count)],
            colors=GPU_COLORS[:gpu_count],
            labels=[f"G{i}" for i in range(gpu_count)])),
        ("cpu", MultiSensorViewer(
            "CPU Temperature",
            sensor_keys=[f"cpu{i}_temp" for i in range(cpu_count)],
            colors=CPU_COLORS[:cpu_count],
            labels=[f"CPU{i}" for i in range(cpu_count)])),
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
        "coolant_inlet1": SensorData(
            "Coolant Inlet1", "\u00b0C", 15, 50,
            read_rate=1, redis=r, redis_key='coolant_temp_inlet1',
            icon="\U000f0510"),
        "coolant_outlet1": SensorData(
            "Coolant Outlet1", "\u00b0C", 15, 60,
            read_rate=1, redis=r, redis_key='coolant_temp_outlet1',
            icon="\U000f0510", label="OUT1"),
        "coolant_delta1": SensorData(
            "Coolant \u0394T1", "\u00b0C", 0, 20,
            read_rate=1, redis=r, redis_key='coolant_delta_t1',
            icon="\U000f0510", label="\u0394T1"),
        "chassis_temp": SensorData(
            "Air Temperature", "\u00b0C", -20, 60,
            read_rate=1, redis=r, redis_key='air_temp',
            icon="\U000f0510"),
        "chassis_humid": SensorData(
            "Chassis Humidity", "%", 0, 100,
            read_rate=1, redis=r, redis_key='air_humit',
            icon="\U000f058e", label="HUM"),
    }


def create_fallback_viewers():
    return [
        ("chassis", SensorViewer("Coolant Loop1",
                     sensor_key="coolant_inlet1",
                     sub1_key="coolant_outlet1",
                     sub2_key="coolant_delta1")),
    ]
