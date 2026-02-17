import threading
import time
import socket
import fcntl
import struct
import configparser

import redis
from PIL import Image, ImageDraw

from config import USE_VIRTUAL_LCD, GRAPH_SIZE, FPS
from profiles import load_product

if USE_VIRTUAL_LCD:
    from config import VirtualLCD
else:
    from config import st7789, spi, cs_pin, dc_pin, reset_pin, BAUDRATE


class DisplayManager:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.horizontal = -1

        self.update_info()
        self.version = "gadgetini v0.3"
        #self.redis = redis.Redis(host='localhost', port=6379, db=0)
        self.redis = redis.Redis(host='192.168.1.64', port=6379, db=0)

        self.viewer_rotation_sec = 5
        self.current_viewer = 0

        product_name = self.config.get('PRODUCT', 'name', fallback='dg5w')
        product = load_product(product_name)

        try:
            self.sensors = product.create_sensors(self.redis)
            self.viewers = product.create_viewers()
        except Exception as e:
            print(f"Sensor init failed: {e}")
            self.sensors = product.create_fallback_sensors(self.redis)
            self.viewers = product.create_fallback_viewers()

        self.stop_event = threading.Event()
        self.ip_addr = ""

    def set_display(self, rotation):
        self.rotation = rotation
        if not USE_VIRTUAL_LCD:
            self.x_offset = 10
            self.y_offset = 50
            self.deadzone_x = 170
            self.deadzone_y = 320

            self.disp = st7789.ST7789(spi,
                rotation=self.rotation,
                cs=cs_pin,
                dc=dc_pin,
                rst=reset_pin,
                baudrate=BAUDRATE,
                x_offset=0, y_offset=0)
        else:
            self.x_offset = 0
            self.y_offset = 0
            self.deadzone_x = 170
            self.deadzone_y = 320

            self.disp = VirtualLCD(
                    (170, 320),
                    (self.x_offset, self.y_offset),
                    (self.deadzone_x, self.deadzone_y),
                    )

        self.horizontal = 1
        if self.rotation % 180 == 0:
            self.width = self.disp.width
            self.height = self.disp.height
            self.horizontal = 0
        else:
            self.height = self.disp.width
            self.width = self.disp.height
            self.horizontal = 1

        self.disp_buffer = Image.new('RGB', (self.width, self.height), 'black')
        self.draw = ImageDraw.Draw(self.disp_buffer)

    def update_display(self):
        orientation = self.config['DISPLAY']['orientation'].lower()

        if orientation == "horizontal":
            if self.horizontal != 1:
                self.set_display(270)
        elif orientation == "vertical":
            if self.horizontal != 0:
                self.set_display(180)
        else:
            print(f"Orientation: {orientation} must be horizontal or vertical")
            return

    def set_next_viewer(self):
        self.current_viewer = self.current_viewer+1
        if self.current_viewer >= len(self.viewers):
            self.current_viewer = 0
        return self.viewers[self.current_viewer]

    def get_cur_viewer(self):
        return self.viewers[self.current_viewer]

    def draw_viewer(self, frame):
        cur_viewer = self.get_cur_viewer()
        cur_viewer.draw(self.draw, self, frame)
        self.disp.image(self.disp_buffer)

    def update_info(self, config_path="config.ini"):
        self.config.read(config_path)
        self.get_ip_address()
        self.update_display()

    def get_ip_address(self):
        interfaces = ["eth0", "wlan0"]
        self.ip_addr = "no network found"

        for ifname in interfaces:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.ip_addr = socket.inet_ntoa(fcntl.ioctl(
                    s.fileno(),
                    0x8915,  # SIOCGIFADDR
                    struct.pack('256s', ifname[:15].encode('utf-8'))
                )[20:24])
                return
            except Exception as e:
                self.ip_addr = "no network found"
                continue

    def sensor_data_collector(self):
        while not self.stop_event.is_set():
            for sensor_data in self.sensors.values():
                if sensor_data.active:
                    sensor_data.sensor_data_collector()
            time.sleep(1/FPS)

    def data_processor(self):
        frame = 0
        while not self.stop_event.is_set():
            for sensor_data in self.sensors.values():
                sensor_data.sensor_data_processing()

            if (frame % (FPS*5)) == 0:
                self.update_info()
            if ((frame != 0) and (frame % (FPS*self.viewer_rotation_sec)) == 0):
                self.set_next_viewer()

            frame = frame + 1
            if frame > FPS*3600*24*7:
                frame = 0

            self.draw_viewer(frame % FPS)
            time.sleep(1/FPS)

    def start_thr(self):
        sensor_thread = threading.Thread(
            target=self.sensor_data_collector
        )
        graph_thread = threading.Thread(
            target=self.data_processor,
        )

        sensor_thread.daemon = True
        graph_thread.daemon = True

        sensor_thread.start()
        graph_thread.start()

        return sensor_thread, graph_thread

    def stop(self):
        self.stop_event.set()
        self.disp.cleanup()
