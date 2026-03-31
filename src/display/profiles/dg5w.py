import os
from profile_loader import load_sensors, load_viewers

_JSON = os.path.join(os.path.dirname(__file__), 'dg5w.json')


def create_sensors(redis, config=None):
    return load_sensors(_JSON, redis, config)


def create_viewers(config=None):
    return load_viewers(_JSON, config)


def create_fallback_sensors(redis):
    from sensor_data import SensorData
    r = redis
    return {
        "coolant_inlet1": SensorData(
            "Coolant Inlet", "\u00b0C", 25, 50,
            read_rate=1, redis=r, redis_key='coolant_temp_inlet1',
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
    from dual_sensor_viewer import DualSensorViewer
    return [
        ("chassis", DualSensorViewer(panels=[
            {"title": "Chassis Temperature", "sensor_key": "chassis_temp"},
            {"title": "Chassis Humidity",    "sensor_key": "chassis_humid"},
        ])),
    ]
