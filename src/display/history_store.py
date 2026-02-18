import json
import os
import time

from config import GRAPH_SIZE


class HistoryStore:
    """Accumulates sensor samples and stores 10-min max values for 24h history."""

    def __init__(self, file_path="history.json", interval_sec=600):
        self.file_path = file_path
        self.interval_sec = interval_sec
        self.max_points = GRAPH_SIZE - 1          # 144 points ≈ 24h at 10-min
        self.history = {}                          # {sensor_key: [max, max, ...]}
        self._accum = {}                           # {sensor_key: [sample, ...]}
        self._last_interval = time.time()
        self.load()

    def accumulate(self, sensor_key, value):
        if sensor_key not in self._accum:
            self._accum[sensor_key] = []
        self._accum[sensor_key].append(value)

    def tick(self):
        now = time.time()
        if now - self._last_interval >= self.interval_sec:
            self._flush()
            self._last_interval = now
            self.save()

    def _flush(self):
        for key, samples in self._accum.items():
            if not samples:
                continue
            peak = max(samples)
            if key not in self.history:
                self.history[key] = []
            self.history[key].append(round(peak, 2))
            if len(self.history[key]) > self.max_points:
                self.history[key].pop(0)
        self._accum = {k: [] for k in self._accum}

    def get_history(self, sensor_key):
        return self.history.get(sensor_key, [])

    def save(self):
        try:
            tmp_path = self.file_path + ".tmp"
            with open(tmp_path, 'w') as f:
                json.dump(self.history, f)
            os.replace(tmp_path, self.file_path)
        except Exception as e:
            print(f"History save failed: {e}")

    def load(self):
        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
            self.history = {k: v[-self.max_points:] for k, v in data.items()}
        except (FileNotFoundError, json.JSONDecodeError):
            self.history = {}
