from adafruit_rgb_display import st7789
import numpy as np

import threading
import queue
import time
import random
import requests


# Blinka CircuitPython
import board
import digitalio
import busio
import RPi.GPIO as GPIO

import socket
import fcntl
import struct

from PIL import Image, ImageDraw, ImageFont


##Sensors
import sys 
sys.path.append('/home/gadgetini/High-Precision-AD-DA-Board-Code/RaspberryPI/ADS1256/python3')
import ADS1256
import adafruit_dht

# Configuration for CS and DC pins (these are PiTFT defaults):)))))
cs_pin = digitalio.DigitalInOut(board.D18)
dc_pin = digitalio.DigitalInOut(board.D26)
reset_pin = digitalio.DigitalInOut(board.D13)

# Config for display baudrate (default max is 24mhz):
BAUDRATE = 24000000

# Setup SPI bus using hardware SPI:
spi = busio.SPI(board.SCK_1,board.MOSI_1,board.MISO_1)


GRAPH_SIZE = 145

FPS = 30

FONT_PATH = "fonts/JetBrainsMono-Regular.ttf"
BOLD_FONT_PATH = "fonts/JetBrainsMono-Bold.ttf"
EXTRABOLD_FONT_PATH = "fonts/JetBrainsMono-ExtraBold.ttf"
LIGHT_FONT_PATH = "fonts/JetBrainsMono-Light.ttf"
THIN_FONT_PATH = "fonts/JetBrainsMono-Thin.ttf"

_font_cache = {}

def get_cached_font(size, font_path=FONT_PATH):
    cache_key = (size, font_path)
    if cache_key in _font_cache:
        return _font_cache[cache_key]
    else:
        font = ImageFont.truetype(font_path, size)
        _font_cache[cache_key] = font
        return font


def get_text_dimensions(draw, text_string, font):
    bbox = draw.textbbox((0,0), text_string, font=font)
    if bbox:
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        ascent = -bbox[1]
        if (ascent % 2 != 0):
            ascent = ascent + 1

        return (width, height, ascent)

    #return font.getsize(text_string) 
#box: (x, y, width, height)
#align: "left", "center", "right"
def draw_aligned_text(draw, text, font_size, fill, box, align="left", halign="top", font_path=FONT_PATH):
    x, y, width, height = box

    font = get_cached_font(font_size, font_path)
    text_width, text_height, ascent = get_text_dimensions(draw, text, font=font)
    new_font_size = font_size

    if text_width > width or text_height > height:
        scale = min(width / text_width, height / text_height)
        new_font_size = max(1, int(font.size * scale))
        font = get_cached_font(new_font_size)
        text_width, text_height, ascent = get_text_dimensions(draw, text, font=font)

    #print("font_size="+str(new_font_size) + " ascent=" + str(ascent))

    if align == "center":
        tx = x + (width - text_width) / 2
    elif align == "right":
        tx = x + (width - text_width)
    else:
        tx = x

    if halign == "top":
        ty = y + ascent
    elif halign == "center":
        ty = y + (height - text_height) / 2 + ascent
    else:
        ty = y + (height - text_height) + ascent

    draw.rectangle((x,y,x+width,y+height), outline=(255,0,0), width=1)
    bbox = draw.textbbox((tx, ty), text, font=font)
    draw.rectangle(bbox, outline=(0,255,0), width=1)

    draw.text((tx, ty), text, font=font, fill=fill)

class SensorData:
    def __init__(self, type_name, unit_str, min_val, max_val, read_rate=30, max_buffer_size=GRAPH_SIZE):
        self.type_name_str = type_name
        self.unit_str = unit_str
        #self.data_queue = queue.Queue(max_buffer_size)
        self.data_queue = queue.Queue(1)
        self.buffer = []
        self.min_val = min_val
        self.max_val = max_val
        self.read_rate = read_rate #Hz
        self.active = 1
        self.lock = threading.Lock()
        self.max_points = GRAPH_SIZE-5
        self.count = 0
        self.prev = 2

    def read_sensor_fake(self):
        r =random.uniform(-2,2)
        value = self.prev + r
#       if value > self.max_val:
#           value = self.max_val
        if value < self.min_val:
            value = self.min_val
        self.prev = value
        return value

    def read_sensor(self):
        return self.read_sensor_fake()

    def sensor_data_collector(self):
        if self.count > self.read_rate:
            self.count = 0
            sensor_value = self.read_sensor()          
            with self.lock:
                if self.data_queue.full():
                    #print(self.type_name_str + "data_queue pop")
                    self.data_queue.get(0)
                if not self.data_queue.full():
                    self.data_queue.put(sensor_value)
        else:
            self.count = self.count + 1

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


class CoolantTemperatureData(SensorData):
    def __init__(self, ADC, type_name, unit_str, min_val, max_val, read_rate=30, max_buffer_size=GRAPH_SIZE):
        super().__init__(type_name, unit_str, min_val, max_val, read_rate, max_buffer_size)
        self.ADC = ADC
    def read_sensor(self):
        return self.get_coolant_temp()

# Coolant temperature fomula generate by several measured data using linear regression. 
# x: Raw sensing data(ADC_Value, y: Degree celcisous)
    def get_coolant_temp(self):
        ADC_Value = self.ADC.ADS1256_GetAll()
        coeff_a = 50.453
        coeff_b = -1.177
        raw = 0
        celcious = 0
        if float(ADC_Value[4]*5.0/0x7fffff) < 1:
            raw = 1.282
            celcious = coeff_a * raw ** coeff_b
        else:
            celcious = coeff_a * float(ADC_Value[4]*5.0/0x7fffff) ** coeff_b
        celcious = round(celcious, 1)
        return celcious

class ChassisHumidData(SensorData):
    def __init__(self, DHT, type_name, unit_str, min_val, max_val, read_rate=30, max_buffer_size=GRAPH_SIZE):
        super().__init__(type_name, unit_str, min_val, max_val, read_rate, max_buffer_size)
        self.DHT = DHT
    def read_sensor(self):
        return self.get_air_humid()

    def get_air_humid(self):
        curr_humid = 25
        try:
            curr_humid = dhtDevice.humidity
            print("humidity = " + str(curr_humid))
        except Exception as e:
            print("dht sensing error")
            # Error happen fairly often, DHT's are hard to read, just keep going 
            #dhtDevice = adafruit_dht.DHT11(board.D4)
            #curr_humit = dhtDevice.humidity
            pass
        finally:
            return curr_humid

class Viewer:
    def __init__(self, title="", active=1):
        self.title = title
        self.active = active

class Chassis_Viewer(Viewer):
    def __init__(self, title="", active=1):
        self.title = title
        self.active = active
        self.type = "Chassis"

    def draw(self, draw, disp_manager):
        draw.rectangle((0, 0, disp_manager.width, disp_manager.height), fill='black')

        sensor_data = disp_manager.disp_data[0]
        if len(sensor_data.buffer) < 2:
            return

        min_value = int(np.min(sensor_data.buffer)*0.95)
        max_value = int(np.max(sensor_data.buffer)*1.05)

        normalized_data = np.interp(
            sensor_data.buffer, 
            #(sensor_data.min_val, sensor_data.max_val), 
            (min_value, max_value), 
            (48, disp_manager.height-55) 
        )

        if disp_manager.horizontal == 0:
            x1 = 50
            x2 = x1 + GRAPH_SIZE
            y1 = 25
            y2 = y1 + GRAPH_SIZE
        else:
            x1 = 10
            x2 = x1 + GRAPH_SIZE
            y1 = 50
            y2 = y1 + GRAPH_SIZE


        gray = (12,12,12)
        draw.line((x1, y1, x2, y1), fill=gray) 
        draw.line((x1, y1, x1, y2), fill=gray) 
        draw.line((x1, y2, x2, y2), fill=gray) 
        draw.line((x2, y1, x2, y2), fill=gray) 

        sensor_value_str = str(f"{round(sensor_data.buffer[-1],2):.1f}")
        title = str(sensor_data.type_name_str)
        unit = str(sensor_data.unit_str)

        min_value_str = str(f"{round(min_value):.1f}"+sensor_data.unit_str)
        max_value_str = str(f"{round(max_value):.1f}"+sensor_data.unit_str)

        if disp_manager.horizontal == 1:
            #TITLE
            draw_aligned_text(draw=draw, text=title, font_size=40, fill=sensor_data.get_color_gradient(sensor_data.buffer[-1]), box=(x1+GRAPH_SIZE+5, y1-8, 159, 30), align="center", halign="center", font_path=BOLD_FONT_PATH)
            #VALUE
            draw_aligned_text(draw=draw, text=sensor_value_str, font_size=55, fill=sensor_data.get_color_gradient(sensor_data.buffer[-1]), box=(x1+GRAPH_SIZE+5, y1+22, 135, 45), align="right", halign="top", font_path=EXTRABOLD_FONT_PATH)
            #UNIT
            draw_aligned_text(draw=draw, text=unit, font_size=40, fill='white', box=(x1+GRAPH_SIZE+5+135, y1+22, 25, 45), align="left", halign="top", font_path=BOLD_FONT_PATH)

            #IP
            draw_aligned_text(draw=draw, text=disp_manager.ip_addr, font_size=10, fill='white', box=(x2, y2, 165, 8), align="right", halign="bottom", font_path=LIGHT_FONT_PATH)


            #CHASSIS Value


            #Min/Max
            draw_aligned_text(draw=draw, text=max_value_str, font_size=10, fill=sensor_data.get_color_gradient(max_value), box=(x1, y1-8, x2-x1, 8), align="center", halign="top", font_path=THIN_FONT_PATH)
            draw_aligned_text(draw=draw, text=min_value_str, font_size=10, fill=sensor_data.get_color_gradient(min_value), box=(x1, y2, x2-x1, 8), align="center", halign="bottom", font_path=THIN_FONT_PATH)

            for i in range(1, len(sensor_data.buffer)):
                px1 = i + x1
                py1 = int(disp_manager.height - normalized_data[i-1])
                px2 = i + x1 + 1
                py2 = int(disp_manager.height - normalized_data[i])
                color = sensor_data.get_color_gradient(sensor_data.buffer[i])
                draw.line((px1,py1,px2,py2), fill=color, width=3)

        else:
            self.draw.text((x1-5, GRAPH_SIZE + 50), sensor_value_str, fill=sensor_data.get_color_gradient(sensor_data.buffer[-1]), font=self.big_font)
            draw_aligned_text(draw=self.draw, text=sensor_value_str, font_size=75, fill=sensor_data.get_color_gradient(sensor_data.buffer[-1]), box=(x1-5, y1+30, 135, 80), align="right", halign="top")


class DisplayManager:
    def __init__(self, rotation=270):
        self.rotation = rotation
        self.disp = st7789.ST7789(spi, # 1.9" ST7789
            rotation=self.rotation,
            cs=cs_pin,
            dc=dc_pin,
            rst=reset_pin,
            baudrate=BAUDRATE,
            x_offset=0, y_offset=0
        )

        self.ADC=ADS1256.ADS1256()
        self.ADC.ADS1256_init()

        #self.DHT = adafruit_dht.DHT11(board.D4)

        self.viewer_rotation_sec = 5 #sec
        self.current_viewer = 0
        self.viewers = []
        self.viewers.append(Chassis_Viewer("Chassis Info")) #0 Viewer

        self.disp_data = []
        #self.disp_data.append(SensorData("CPU Temperature", "°C", 0, 20, 1))
        #self.disp_data.append(SensorData("CPU Utilization", "%", 0, 100, 10))
        #self.disp_data.append(SensorData("GPU Temperature", "°C", 0, 120, 10))
        #self.disp_data.append(SensorData("GPU Utilization", "%", 0, 100, 10))
        #self.disp_data.append(SensorData("RAM Utilization", "%", 0, 100, 10))
        #self.disp_data.append(SensorData("HDD Utilization", "%", 0, 100, 10))
        self.disp_data.append(CoolantTemperatureData(self.ADC, "Coolant Temperature", "°C", 20, 60, 10))  #0 Data
        #self.disp_data.append(ChassisHumidData(self.DHT, "Chassis Humid", "%", 10, 80, 1))         #1 Data
        #self.disp_data.append(SensorData("Chassis Temperature", "°C", 0, 50, 1))   #2 Data

        self.stop_event = threading.Event()
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
        
        self.ip_addr = ""

        try:
            #self.font = ImageFont.truetype(FONT_PATH, 20)
            self.font = get_cached_font(20)
            self.mid_font = get_cached_font(40)
            self.big_font = get_cached_font(80)
            self.small_font = get_cached_font(12)
            #self.mid_font = ImageFont.truetype("fonts/PretendardVariable.ttf", 40)
            #self.big_font = ImageFont.truetype("fonts/PretendardVariable.ttf", 80)
            #self.small_font = ImageFont.truetype("fonts/PretendardVariable.ttf", 12)
        except Exception as e:
            print("Cannot find font!")
            return



    def read_sensor(self):
        try:
            chassis_temp_query = 'DLC_sensors_gauge{metric="Chassis temperature"}'
            chassis_temp_response = requests.get('http://192.168.1.145:9090/api/v1/query', params={'query': chassis_temp_query})
            chassis_temp_response = chassis_temp_response.json()['data']['result']
            temp = float(chassis_temp_response[-1]['value'][-1])
            print(temp)
            return temp
        except Exception as e:
            return 0

    def set_next_viewer(self):
        self.current_viewer = self.current_viewer+1
        if self.current_viewer >= len(self.viewers):
            self.current_viewer = 0
        return self.viewers[self.current_viewer]

    def get_cur_viewer(self):
        return self.viewers[self.current_viewer]

    def draw_viewer(self, frame):
        cur_viewer = self.get_cur_viewer()
        cur_viewer.draw(self.draw, self)
        self.disp.image(self.disp_buffer)

    def update_info(self):
        self.get_ip_address()

    def get_ip_address(self, ifname="eth0"):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ip_addr = socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15].encode('utf-8'))
        )[20:24])
        #self.ip_addr = '.'.join(octet.zfill(3) for octet in ip.split('.'))

    def sensor_data_collector(self):
        while not self.stop_event.is_set():
            for sensor_data in self.disp_data:
                if sensor_data.active:
                    sensor_data.sensor_data_collector()
            time.sleep(1/FPS)  # ~30Hz

    def data_processor(self):
        frame = 0
        while not self.stop_event.is_set():
            for sensor_data in self.disp_data:
                sensor_data.sensor_data_processing()

            if (frame % (FPS*5)) == 0: # 5 sec
                self.update_info()
            if ((frame != 0) and (frame % (FPS*self.viewer_rotation_sec)) == 0): # 20 sec
                self.set_next_viewer()
            
            frame = frame + 1
            if frame > FPS*3600*24*7:
                frame = 0

            self.draw_viewer(frame % FPS)
            time.sleep(1/FPS)  # ~30fps

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

def main():
    try:
        display_manager = DisplayManager(rotation=270)
        sensor_thread, graph_thread = display_manager.start_thr()

        sensor_thread.join()
        graph_thread.join()
    except KeyboardInterrupt:
        print("Quit")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()


