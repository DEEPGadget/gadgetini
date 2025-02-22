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

from PIL import Image, ImageDraw, ImageFont

# Configuration for CS and DC pins (these are PiTFT defaults):)))))
cs_pin = digitalio.DigitalInOut(board.D18)
dc_pin = digitalio.DigitalInOut(board.D26)
reset_pin = digitalio.DigitalInOut(board.D13)

# Config for display baudrate (default max is 24mhz):
BAUDRATE = 24000000

# Setup SPI bus using hardware SPI:
spi = busio.SPI(board.SCK_1,board.MOSI_1,board.MISO_1)


GRAPH_SIZE = 145


class DispData:
    def __init__(self, max_buffer_size=GRAPH_SIZE):
        self.data_queues = []
        self.data_queues.append(queue.Queue(max_buffer_size))



class SensorGraphRenderer:
    def __init__(self, rotation=180):
        self.rotation = rotation
        self.disp = st7789.ST7789(spi, # 1.9" ST7789
            rotation=self.rotation,
            cs=cs_pin,
            dc=dc_pin,
            rst=reset_pin,
            baudrate=BAUDRATE,
            x_offset=0, y_offset=0
        )
        self.disp_data = DispData()
        self.data_queue = self.disp_data.data_queues[0]

        self.lock = threading.Lock()
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
        self.max_points = GRAPH_SIZE
        self.draw = ImageDraw.Draw(self.disp_buffer)
        
        self.horizontal_buffer = []


        self.prev = 2
   
        try:
            self.font = ImageFont.truetype("/home/gadgetini/gadgetini/src/display/fonts/public/variable/PretendardVariable.ttf", 10)
            self.big_font = ImageFont.truetype("/home/gadgetini/gadgetini/src/display/fonts/public/variable/PretendardVariable.ttf", 80)
        except Exception as e:
            print("Cannot find font!")
            return

    def get_color_gradient(self, value, min_val=10, max_val=60):
        ratio = max(0, min(1, (value - min_val) / (max_val - min_val)))
        r = int(255 * ratio)
        b = int(255 * (1 - ratio))
        return (r, 0, b)

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
    def read_sensor_fake(self):
            r =random.uniform(-2,2)

            value = self.prev + r
            if value > 60:
                value = 60
            if value < 10:
                value = 10

            self.prev = value

            #print("value = ", value, "\n")
            return value

        #return random.uniform(10, 60)

    def draw_graph(self):
        self.draw.rectangle((0, 0, self.width, self.height), fill='black')
        #print(self.width, self.height)


        #self.draw.rectangle((0, 0, self.height, self.width), fill='black')
        #self.draw.rectangle((50, 0, 100, 150), fill='white')
        if len(self.horizontal_buffer) < 2:
            return

        min_value = int(np.min(self.horizontal_buffer)-1)
        max_value = int(np.max(self.horizontal_buffer)+1)

        normalized_data = np.interp(
            self.horizontal_buffer, 
            (min_value, max_value), 
            (55, self.height-55) 
        )


        if self.horizontal == 0:
            x1 = 50
            x2 = x1 + GRAPH_SIZE
            y1 = 25
            y2 = y1 + GRAPH_SIZE
        else:
            x1 = 10
            x2 = x1 + GRAPH_SIZE
            y1 = 50
            y2 = y1 + GRAPH_SIZE



        self.draw.line((x1, y1, x2, y1), fill='white') 
        self.draw.line((x1, y1, x1, y2), fill='white') 
        self.draw.line((x1, y2, x2, y2), fill='white') 
        self.draw.line((x2, y1, x2, y2), fill='white') 

        #self.draw.text((0, 45), str(int(max_value)), fill='white')
        #self.draw.text((0, self.height-55), str(int(min_value)), fill='white')

        if self.horizontal == 1:
            self.draw.text((x1+GRAPH_SIZE+5, y1+20), str(f"{round(self.horizontal_buffer[-1],2):.1f}"), fill=self.get_color_gradient(self.horizontal_buffer[-1]), font=self.big_font)
        else:
            self.draw.text((x1-5, GRAPH_SIZE + 50), str(f"{round(self.horizontal_buffer[-1],2):.1f}"), fill=self.get_color_gradient(self.horizontal_buffer[-1]), font=self.big_font)


 #       for i in range(1, len(self.horizontal_buffer)):
 #           x1 = i - 1 + 20
 #           y1 = int(self.height - normalized_data[i-1])
 #           x2 = i + 20
 #           y2 = int(self.height - normalized_data[i])
 #           color = self.get_color_gradient(self.horizontal_buffer[i])
 #           self.draw.line((x1,y1,x2,y2), fill=color, width=4)

        self.disp.image(self.disp_buffer)

    def draw_horizontal_graph(self):
        image = self.disp_buffer
        image.fill((0, 0, 0))

        if len(self.horizontal_buffer) < 2:
            return

        normalized_data = np.interp(
            self.horizontal_buffer, 
            (10, 60), 
            (0, 240) 
        )

        for i in range(1, len(self.horizontal_buffer)):
            y = i
            width = int(normalized_data[i])
            color = self.get_color_gradient(self.horizontal_buffer[i])
            
            for x in range(width):
                image.pixel(x, y, color)

        self.disp.display(image)

    def sensor_data_collector(self):
        while not self.stop_event.is_set():
            sensor_value = self.read_sensor_fake()
            
            with self.lock:
                if self.data_queue.full():
                    self.data_queue.pop(0)

                if not self.data_queue.full():
                    self.data_queue.put(sensor_value)
            
            #time.sleep(0.033)  # ~30Hz
            time.sleep(0.05)  # ~30Hz

    def data_processor(self, graph_type='horizontal'):
        while not self.stop_event.is_set():
            with self.lock:
                while not self.data_queue.empty():
                    value = self.data_queue.get()
                    if graph_type == 'horizontal':
                        self.horizontal_buffer.append(value)
                        if len(self.horizontal_buffer) > self.max_points:
                            self.horizontal_buffer.pop(0)
                        #self.draw_horizontal_graph()
                        self.draw_graph()
                    
                    else:
                        self.vertical_buffer.append(value)
                        if len(self.vertical_buffer) > self.max_points:
                            self.vertical_buffer.pop(0)
                        self.draw_vertical_graph()
            time.sleep(0.033)  # ~30fps

    def start_thr(self, graph_type='horizontal'):
        sensor_thread = threading.Thread(
            target=self.sensor_data_collector
        )
        graph_thread = threading.Thread(
            target=self.data_processor, 
            kwargs={'graph_type': graph_type}
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
        horizontal_manager = SensorGraphRenderer()
        h_sensor_thread, h_graph_thread = horizontal_manager.start_thr(graph_type='horizontal')

        h_sensor_thread.join()
        h_graph_thread.join()
    except KeyboardInterrupt:
        print("Quit")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()


