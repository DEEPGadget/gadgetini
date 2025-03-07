import numpy as np

import threading
import queue
import time
import random
import requests


import socket
import fcntl
import struct

from PIL import Image, ImageDraw, ImageFont
import redis


#For Debugging
DEBUG = 1
USE_VIRTUAL_LCD = True
USE_REAL_DATA = False

if USE_VIRTUAL_LCD:
    from virtual_lcd import VirtualLCD
    import cv2
else :
    from adafruit_rgb_display import st7789
    # Blinka CircuitPython
    import board
    import digitalio
    import busio
    import RPi.GPIO as GPIO

    # Configuration for CS and DC pins (these are PiTFT defaults):)))))
    cs_pin = digitalio.DigitalInOut(board.D18)
    dc_pin = digitalio.DigitalInOut(board.D26)
    reset_pin = digitalio.DigitalInOut(board.D13)

    # Config for display baudrate (default max is 24mhz):
    BAUDRATE = 24000000
    # Setup SPI bus using hardware SPI:
    spi = busio.SPI(board.SCK_1,board.MOSI_1,board.MISO_1)



import configparser


##Sensors
#import sys 
#sys.path.append('/home/gadgetini/High-Precision-AD-DA-Board-Code/RaspberryPI/ADS1256/python3')
#import ADS1256
#import adafruit_dht





GRAPH_SIZE = 145

FPS = 10

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
def draw_aligned_text(draw, text, font_size, fill, box, align="left", halign="top", font_path=FONT_PATH, autoscale=False):
    x, y, width, height = box

    font = get_cached_font(font_size, font_path)
    text_width, text_height, ascent = get_text_dimensions(draw, text, font=font)
    new_font_size = font_size

    if (autoscale == True) and (text_width > width or text_height > height):
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

    if DEBUG != 0:
        draw.rectangle((x,y,x+width,y+height), outline=(255,0,0), width=1)
        bbox = draw.textbbox((tx, ty), text, font=font)
        draw.rectangle(bbox, outline=(0,255,0), width=1)

    draw.text((tx, ty), text, font=font, fill=fill)

class SensorData:
    def __init__(self, title_str, unit_str, min_val, max_val, read_rate=30, max_buffer_size=GRAPH_SIZE):
        self.title_str = title_str
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
        #print("value = " + str(value))
        return value

    def read_sensor(self):
        return self.read_sensor_fake()

    def sensor_data_collector(self):
        if self.count >= self.read_rate:
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
    def __init__(self, title_str, unit_str, min_val, max_val, read_rate=30, max_buffer_size=GRAPH_SIZE, redis=None):
        super().__init__(title_str, unit_str, min_val, max_val, read_rate, max_buffer_size)
        #print(f"read_rate={self.read_rate}")
        self.redis = redis
    
    def read_sensor(self):
        #print("read_sensor")
        if not USE_REAL_DATA:
            return self.read_sensor_fake()
        return self.get_coolant_temp()

    def get_coolant_temp(self):
        celcious = float(self.redis.get('coolant_temp'))
        #print(f"celcious = {celcious}")
        return celcious

class ChassisHumidData(SensorData):
    def __init__(self, title_str, unit_str, min_val, max_val, read_rate=30, max_buffer_size=GRAPH_SIZE, redis=None):
        super().__init__(title_str, unit_str, min_val, max_val, read_rate, max_buffer_size)
        self.redis = redis

    def read_sensor(self):
        if not USE_REAL_DATA:
            return self.read_sensor_fake()

        return self.get_air_humid()

    def get_air_humid(self):
        humid = float(self.redis.get('air_humit'))
        return humid

class ChassisTemperatureData(SensorData):
    def __init__(self, title_str, unit_str, min_val, max_val, read_rate=30, max_buffer_size=GRAPH_SIZE, redis=None):
        super().__init__(title_str, unit_str, min_val, max_val, read_rate, max_buffer_size)
        self.redis = redis

    def read_sensor(self):
        if not USE_REAL_DATA:
            return self.read_sensor_fake()

        return self.get_air_temp()

    def get_air_temp(self):
        humid = float(self.redis.get('air_temp'))
        return humid


class Viewer:
    def __init__(self, title="", active=1):
        self.title = title
        self.active = active

        self.frameSize = (240, 240)
        self.xyCoord = [10, 0]
        self.isUp = True
        self.colors = ["red", "orange", "yellow", "green", "blue", "magenta", "white", "cyan"]
        self.color_index = 0

        self.image_buffer = Image.new('RGB', self.frameSize, color=(0, 0, 0))
        self.draw_object = ImageDraw.Draw(self.image_buffer)

    def draw(self, draw2, disp_manager):
            self.image_buffer = disp_manager.disp_buffer
            self.draw_object = draw2

        #while True:
            
            #draw = ImageDraw.Draw(self.image)
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            self.draw_object.text((self.xyCoord[0], self.xyCoord[1]), "Hello World!", font=font, fill=self.colors[self.color_index])

            if self.isUp:
                self.xyCoord[1] += 2
                if self.xyCoord[1] >= self.frameSize[1] - 30:
                    self.isUp = False
                    self.color_index = (self.color_index + 1) % len(self.colors)
            else:
                self.xyCoord[1] -= 2
                if self.xyCoord[1] <= 0:
                    self.isUp = True
                    self.color_index = (self.color_index + 1) % len(self.colors)

            #cv_image = cv2.cvtColor(np.array(self.image_buffer), cv2.COLOR_RGB2BGR)

            #cv2.imshow("Virtual Display", cv_image)

            key = cv2.waitKey(30)
            #if key == 27:  # ESC
                #break

        #cv2.destroyAllWindows()


class Chassis_Viewer(Viewer):
    def __init__(self, title="", active=1):
        self.title = title
        self.active = active
        self.type = "Chassis"

    def draw(self, draw, disp_manager, frame):
        if disp_manager.horizontal == 1:
            offset = (disp_manager.x_offset, disp_manager.y_offset)
        else:
            offset = (disp_manager.y_offset, disp_manager.x_offset)

        draw.rectangle((0, 0, disp_manager.width, disp_manager.height), fill='black')
        if DEBUG != 0:
            draw.rectangle((offset[0],offset[1],disp_manager.width, disp_manager.height), outline=(0,0,255), width=3)

        coolant_temp_data = disp_manager.disp_data[0]
        chassis_humid_data = disp_manager.disp_data[1]
        chassis_temp_data = disp_manager.disp_data[2]

        sensor_data = coolant_temp_data     #main sensor
        sub_sensor_data_1 = chassis_humid_data  #sub sensor 1
        sub_sensor_data_2 = chassis_temp_data   #sub sensor 2

        if len(sensor_data.buffer) < 2:
            print("Ready for reading the sensor data")
            return
        
        #print(str(disp_manager.width) + ", " + str(disp_manager.height))

        min_value = int(np.min(sensor_data.buffer)*0.95)
        max_value = int(np.max(sensor_data.buffer)*1.05)

        normalized_data = np.interp(
            sensor_data.buffer, 
            (min_value, max_value), 
            #(48, disp_manager.height-55) 
            (8, GRAPH_SIZE-8) 
        )

        gray = (50,50,50)

        #GRAPHBOX
        graphbox_x1 = offset[0]
        graphbox_y1 = offset[1]
        graphbox_x2 = graphbox_x1 + GRAPH_SIZE
        graphbox_y2 = graphbox_y1 + GRAPH_SIZE
        if DEBUG == 1:
            draw.rectangle((graphbox_x1, graphbox_y1, graphbox_x2, graphbox_y2), outline=gray, width=3)


        #DATABOX
        if disp_manager.horizontal == 1:
            databox_x1 = graphbox_x2 + 5
            databox_y1 = graphbox_y1
            databox_x2 = databox_x1 + GRAPH_SIZE
            databox_y2 = databox_y1 + GRAPH_SIZE
        else:
            databox_x1 = graphbox_x1
            databox_y1 = graphbox_y2 + 5
            databox_x2 = databox_x1 + GRAPH_SIZE
            databox_y2 = databox_y1 + GRAPH_SIZE
        
        if DEBUG == 1:
            draw.rectangle((databox_x1, databox_y1, databox_x2, databox_y2), outline=gray, width=3)

        sensor_value_str = str(f"{round(sensor_data.buffer[-1],2):.1f}")
        title = str(sensor_data.title_str)
        unit = str(sensor_data.unit_str)

        min_value_str = str(f"{round(min_value):.1f}"+sensor_data.unit_str)
        max_value_str = str(f"{round(max_value):.1f}"+sensor_data.unit_str)

        version_str = str(disp_manager.version)

        #TITLE
        draw_aligned_text(draw=draw, text=title, font_size=40, fill=sensor_data.get_color_gradient(sensor_data.buffer[-1]), box=(databox_x1, databox_y1, databox_x2-databox_x1, 30), align="center", halign="center", font_path=BOLD_FONT_PATH, autoscale=True)
        #VALUE
        draw_aligned_text(draw=draw, text=sensor_value_str, font_size=50, fill=sensor_data.get_color_gradient(sensor_data.buffer[-1]), box=(databox_x1, databox_y1+30, (databox_x2-databox_x1-25), 45), align="right", halign="top", font_path=EXTRABOLD_FONT_PATH)
        #UNIT
        draw_aligned_text(draw=draw, text=unit, font_size=40, fill='white', box=(databox_x2-25, databox_y1+30, 25, 45), align="left", halign="top", font_path=BOLD_FONT_PATH, autoscale=True)

        #IP
        draw_aligned_text(draw=draw, text=disp_manager.ip_addr, font_size=8, fill='white', box=(databox_x1, databox_y2-12, GRAPH_SIZE, 12), align="left", halign="center", font_path=LIGHT_FONT_PATH)

        #Gadgetini Version
        draw_aligned_text(draw=draw, text=version_str, font_size=8, fill='gray', box=(databox_x1, databox_y2-12, GRAPH_SIZE, 12), align="right", halign="center", font_path=LIGHT_FONT_PATH)


        margin=5
        #CHASSIS Value
        if len(sub_sensor_data_1.buffer) > 0:
            draw_aligned_text(draw=draw, text=sub_sensor_data_1.title_str, font_size=6, fill='white', box=(databox_x1, databox_y1+75, (databox_x2-databox_x1)/2-margin, 15), align="center", halign="center", font_path=THIN_FONT_PATH, autoscale=False)
            draw_aligned_text(draw=draw, text=str(f"{round(sub_sensor_data_1.buffer[-1],2):.1f}"), font_size=26, fill='white', box=(databox_x1, databox_y1+90, (databox_x2-databox_x1)/2-margin, 24), align="right", halign="top", font_path=BOLD_FONT_PATH)
            draw_aligned_text(draw=draw, text=sub_sensor_data_1.unit_str, font_size=15, fill='white', box=(databox_x1+(databox_x2-databox_x1)/2-25, databox_y1+115, 25-2-margin, 15), align="right", halign="top", font_path=FONT_PATH, autoscale=False)


        if len(sub_sensor_data_2.buffer) > 0:
            draw_aligned_text(draw=draw, text=sub_sensor_data_2.title_str, font_size=6, fill='white', box=(databox_x1+(databox_x2-databox_x1)/2+margin, databox_y1+75, (databox_x2-databox_x1)/2-margin, 15), align="center", halign="center", font_path=THIN_FONT_PATH, autoscale=False)
            draw_aligned_text(draw=draw, text=str(f"{round(sub_sensor_data_2.buffer[-1],2):.1f}"), font_size=26, fill='white', box=(databox_x1+(databox_x2-databox_x1)/2+margin, databox_y1+90, (databox_x2-databox_x1)/2-margin, 24), align="right", halign="top", font_path=BOLD_FONT_PATH)
            draw_aligned_text(draw=draw, text=sub_sensor_data_2.unit_str, font_size=15, fill='white', box=(databox_x1+(databox_x2-databox_x1)-25+margin, databox_y1+115, 25-2-margin, 15), align="right", halign="top", font_path=FONT_PATH, autoscale=False)




        #Min/Max
        draw_aligned_text(draw=draw, text=max_value_str, font_size=8, fill=sensor_data.get_color_gradient(max_value), box=(graphbox_x1, graphbox_y1, GRAPH_SIZE, 8), align="center", halign="top", font_path=FONT_PATH)
        draw_aligned_text(draw=draw, text=min_value_str, font_size=8, fill=sensor_data.get_color_gradient(min_value), box=(graphbox_x1, graphbox_y2-8, GRAPH_SIZE, 8), align="center", halign="bottom", font_path=FONT_PATH)

        for i in range(1, len(sensor_data.buffer)):
            px1 = i + graphbox_x1
            py1 = int(graphbox_y2 - normalized_data[i-1])
            px2 = i + graphbox_x1 + 1
            py2 = int(graphbox_y2 - normalized_data[i])
            color = sensor_data.get_color_gradient(sensor_data.buffer[i])
            draw.line((px1,py1,px2,py2), fill=color, width=3)

        
class DisplayManager:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.horizontal = -1

        self.update_info()
        self.version = "gadgetini v0.3"
        self.redis = redis.Redis(host='localhost', port=6379, db=0)

        self.viewer_rotation_sec = 5 #sec
        self.current_viewer = 0
        self.viewers = []
        self.viewers.append(Chassis_Viewer("Chassis Info")) #0 Viewer
        #self.viewers.append(Viewer("Chassis Info")) #0 Viewer

        self.disp_data = []
        self.disp_data.append(CoolantTemperatureData("Coolant Temperature", "°C", 25, 50, read_rate=1, redis=self.redis))
        self.disp_data.append(ChassisHumidData("Chassis Humidity", "%", 0, 100, 1, redis=self.redis))
        self.disp_data.append(ChassisTemperatureData("Chassis Temperature", "°C", -20, 60, 1, redis=self.redis))
        #self.disp_data.append(SensorData("CPU Temperature", "°C", 0, 20, 1))
        #self.disp_data.append(SensorData("CPU Utilization", "%", 0, 100, 10))
        #self.disp_data.append(SensorData("GPU Temperature", "°C", 0, 120, 10))
        #self.disp_data.append(SensorData("GPU Utilization", "%", 0, 100, 10))
        #self.disp_data.append(SensorData("RAM Utilization", "%", 0, 100, 10))
        #self.disp_data.append(SensorData("HDD Utilization", "%", 0, 100, 10))
        #self.disp_data.append(CoolantTemperatureData(self.ADC, "Coolant Temperature", "°C", 20, 60, 10))  #0 Data
        #self.disp_data.append(ChassisHumidData(self.DHT, "Chassis Humid", "%", 10, 80, 1))         #1 Data
        #self.disp_data.append(SensorData("Chassis Temperature", "°C", 0, 50, 1))   #2 Data

        self.stop_event = threading.Event()
       
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

    def set_display(self, rotation):
        self.rotation = rotation
        if not USE_VIRTUAL_LCD:
            self.x_offset = 10 
            self.y_offset = 50
            self.deadzone_x = 170
            self.deadzone_y = 320

            self.disp = st7789.ST7789(spi, # 1.9" ST7789
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
                    ) #170x320
 
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

    def read_sensor(self):
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
        display_manager = DisplayManager()
        sensor_thread, graph_thread = display_manager.start_thr()

        sensor_thread.join()
        graph_thread.join()
    except KeyboardInterrupt:
        print("Quit")
    finally:
        if not USE_VIRTUAL_LCD:
            GPIO.cleanup()
        else:
            cv2.destroyAllWindows()

if __name__ == "__main__":
    main()


