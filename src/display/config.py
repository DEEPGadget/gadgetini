# Global flags
DEBUG = 0
USE_VIRTUAL_LCD = False
USE_REAL_DATA = True

# Display constants
GRAPH_SIZE = 145
FPS = 15

# Font paths
FONT_PATH = "fonts/JetBrainsMono-Regular.ttf"
BOLD_FONT_PATH = "fonts/JetBrainsMono-Bold.ttf"
EXTRABOLD_FONT_PATH = "fonts/JetBrainsMono-ExtraBold.ttf"
LIGHT_FONT_PATH = "fonts/JetBrainsMono-Light.ttf"
THIN_FONT_PATH = "fonts/JetBrainsMono-Thin.ttf"
ICON_FONT_PATH = "fonts/JetBrainsMonoNerdFont-Bold.ttf"

# Conditional hardware imports
if USE_VIRTUAL_LCD:
    from virtual_lcd import VirtualLCD
    import cv2
else:
    from adafruit_rgb_display import st7789
    import board
    import digitalio
    import busio
    import RPi.GPIO as GPIO

    cs_pin = digitalio.DigitalInOut(board.D18)
    dc_pin = digitalio.DigitalInOut(board.D26)
    reset_pin = digitalio.DigitalInOut(board.D13)

    BAUDRATE = 24000000
    spi = busio.SPI(board.SCK_1, board.MOSI_1, board.MISO_1)
