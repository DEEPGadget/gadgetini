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

        pad = 4
        box_w = w - pad * 2

        if disp_manager.horizontal == 1:
            # Horizontal: 320×170
            draw_aligned_text(
                draw=draw, text="WARNING", font_size=60, fill=text_color,
                box=(pad, h // 2 - 30, box_w, 60),
                align="center", halign="center",
                font_path=EXTRABOLD_FONT_PATH, autoscale=True)

            draw_aligned_text(
                draw=draw, text="COOLANT LEAK DETECTED", font_size=14, fill=text_color,
                box=(pad, h // 2 + 30, box_w, 20),
                align="center", halign="center",
                font_path=BOLD_FONT_PATH, autoscale=True)
        else:
            # Vertical: 170×320
            draw_aligned_text(
                draw=draw, text="WARNING", font_size=34, fill=text_color,
                box=(pad, h // 2 - 30, box_w, 40),
                align="center", halign="center",
                font_path=EXTRABOLD_FONT_PATH, autoscale=True)

            draw_aligned_text(
                draw=draw, text="COOLANT LEAK", font_size=14, fill=text_color,
                box=(pad, h // 2 + 15, box_w, 18),
                align="center", halign="center",
                font_path=BOLD_FONT_PATH, autoscale=True)

            draw_aligned_text(
                draw=draw, text="DETECTED", font_size=14, fill=text_color,
                box=(pad, h // 2 + 33, box_w, 18),
                align="center", halign="center",
                font_path=BOLD_FONT_PATH, autoscale=True)
