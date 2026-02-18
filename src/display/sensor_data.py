import threading
import queue
import random

from config import USE_REAL_DATA, GRAPH_SIZE


class SensorData:
    def __init__(self, title_str, unit_str, min_val, max_val, read_rate=30,
                 max_buffer_size=GRAPH_SIZE, redis=None,
                 redis_key=None, redis_keys=None, formula=None, icon=None, label=None):
        self.title_str = title_str
        self.unit_str = unit_str
        self.icon = icon
        self.label = label
        self.data_queue = queue.Queue(1)
        self.buffer = []
        self.min_val = min_val
        self.max_val = max_val
        self.read_rate = read_rate
        self.active = 1
        self.lock = threading.Lock()
        self.max_points = GRAPH_SIZE - 5
        self.count = 0
        self.prev = 2

        self.redis = redis
        self.redis_key = redis_key
        self.redis_keys = redis_keys
        self.formula = formula
        self.error = False

    def read_sensor_fake(self):
        r = random.uniform(-2, 2)
        value = self.prev + r
        if value < self.min_val:
            value = self.min_val
        self.prev = value
        return value

    def read_sensor(self):
        if not USE_REAL_DATA:
            return self.read_sensor_fake()

        try:
            if self.formula:
                val = self.formula(self.redis)
            elif self.redis_keys:
                max_val = None
                for key in self.redis_keys:
                    try:
                        v = float(self.redis.get(key))
                        if max_val is None or v > max_val:
                            max_val = v
                    except (TypeError, ValueError):
                        continue
                val = max_val
            elif self.redis_key:
                raw = self.redis.get(self.redis_key)
                val = float(raw) if raw is not None else None
            else:
                return self.read_sensor_fake()

            if val is None:
                raise ValueError("no valid data")
            self.error = False
            return val
        except (TypeError, ValueError):
            self.error = True
            return None

    def sensor_data_collector(self):
        self.count += 1
        if self.count >= self.read_rate:
            self.count = 0
            sensor_value = self.read_sensor()
            if sensor_value is None:
                return
            with self.lock:
                if self.data_queue.full():
                    self.data_queue.get(0)
                if not self.data_queue.full():
                    self.data_queue.put(sensor_value)

    def sensor_data_processing(self):
        with self.lock:
            while not self.data_queue.empty():
                value = self.data_queue.get()
                self.buffer.append(value)
                if len(self.buffer) > self.max_points:
                    self.buffer.pop(0)

    def get_color_gradient(self, value):
        ratio = max(0, min(1, (value - self.min_val) / (self.max_val - self.min_val)))
        r = int(255 * ratio)
        b = int(255 * (1 - ratio))
        return (r, 0, b)
