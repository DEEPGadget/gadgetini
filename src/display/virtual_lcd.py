import time
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np

class VirtualLCD:
    def __init__(self, wh, offset, deadzone):
        self.frameSize = wh
        self.width = wh[0]
        self.height = wh[1]
        self.x_offset = offset[0]
        self.y_offest = offset[1]
        self.x_deadzone = deadzone[0]
        self.y_deadzone = deadzone[1]

    def image(self, image_buffer):
        cv_image = cv2.cvtColor(np.array(image_buffer), cv2.COLOR_RGB2BGR)
        cv2.imshow("Virtual ", cv_image)
        key = cv2.waitKey(1)
