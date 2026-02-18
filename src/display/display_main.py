from config import USE_VIRTUAL_LCD

if USE_VIRTUAL_LCD:
    from config import cv2
else:
    from config import GPIO

from display_manager import DisplayManager


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
