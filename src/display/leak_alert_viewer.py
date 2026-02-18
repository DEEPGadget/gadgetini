from config import BOLD_FONT_PATH, EXTRABOLD_FONT_PATH
from draw_utils import draw_aligned_text


class LeakAlertViewer:
    """Fullscreen flashing leak warning. Overrides all normal viewers."""

    def draw(self, draw, disp_manager, frame):
        w = disp_manager.width
        h = disp_manager.height
        flash_on = frame < 5  # 1Hz blink at 10 FPS

        if flash_on:
            bg = (200, 0, 0)
            text_color = 'white'
        else:
            bg = 'black'
            text_color = (200, 0, 0)

        draw.rectangle((0, 0, w, h), fill=bg)

        draw_aligned_text(
            draw=draw, text="WARNING", font_size=60, fill=text_color,
            box=(0, h // 2 - 30, w, 60),
            align="center", halign="center",
            font_path=EXTRABOLD_FONT_PATH)

        draw_aligned_text(
            draw=draw, text="COOLANT LEAK DETECTED", font_size=14, fill=text_color,
            box=(0, h // 2 + 30, w, 20),
            align="center", halign="center",
            font_path=BOLD_FONT_PATH, autoscale=True)
