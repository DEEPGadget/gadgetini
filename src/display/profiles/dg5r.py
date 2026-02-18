import os
from profile_loader import load_sensors, load_viewers

_JSON = os.path.join(os.path.dirname(__file__), 'dg5r.json')


def create_sensors(redis, config=None):
    return load_sensors(_JSON, redis, config)


def create_viewers(config=None):
    return load_viewers(_JSON, config)


def create_fallback_sensors(redis):
    """Minimal safe sensors (hardcoded fallback)."""
    from sensor_data import SensorData
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
    from dual_sensor_viewer import DualSensorViewer
    return [
        ("chassis", DualSensorViewer(panels=[
            {"title": "Air Temperature", "sensor_key": "chassis_temp"},
            {"title": "Humidity", "sensor_key": "chassis_humid"},
        ])),
    ]
