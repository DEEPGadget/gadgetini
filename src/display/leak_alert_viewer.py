from config import (GRAPH_SIZE, BOLD_FONT_PATH, EXTRABOLD_FONT_PATH,
                    LIGHT_FONT_PATH)
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

        # Flash the whole buffer; only the text has to stay on-panel.
        draw.rectangle((0, 0, w, h), fill=bg)

        # The panel shows a window inset by (x_offset, y_offset) into the
        # buffer, so anchor text to the same content box the other viewers
        # lay out in (see BaseViewer._setup / _boxes). Using raw w/h here
        # pushes the footer off the visible area.
        pad = 4
        footer_h = 10
        if disp_manager.horizontal == 1:
            ox, oy = disp_manager.x_offset, disp_manager.y_offset
            area_w, area_h = GRAPH_SIZE * 2 + 5, GRAPH_SIZE
        else:
            ox, oy = disp_manager.y_offset, disp_manager.x_offset
            area_w, area_h = GRAPH_SIZE, GRAPH_SIZE * 2 + 5

        box_x = ox + pad
        box_w = area_w - pad * 2
        cy = oy + area_h // 2

        if disp_manager.horizontal == 1:
            # Horizontal: 295×145 content area
            draw_aligned_text(
                draw=draw, text="WARNING", font_size=60, fill=text_color,
                box=(box_x, cy - 52, box_w, 60),
                align="center", halign="center",
                font_path=EXTRABOLD_FONT_PATH, autoscale=True)

            draw_aligned_text(
                draw=draw, text="COOLANT LEAK DETECTED", font_size=14, fill=text_color,
                box=(box_x, cy + 16, box_w, 20),
                align="center", halign="center",
                font_path=BOLD_FONT_PATH, autoscale=True)
        else:
            # Vertical: 145×295 content area
            draw_aligned_text(
                draw=draw, text="WARNING", font_size=34, fill=text_color,
                box=(box_x, cy - 45, box_w, 40),
                align="center", halign="center",
                font_path=EXTRABOLD_FONT_PATH, autoscale=True)

            draw_aligned_text(
                draw=draw, text="COOLANT LEAK", font_size=14, fill=text_color,
                box=(box_x, cy + 5, box_w, 18),
                align="center", halign="center",
                font_path=BOLD_FONT_PATH, autoscale=True)

            draw_aligned_text(
                draw=draw, text="DETECTED", font_size=14, fill=text_color,
                box=(box_x, cy + 23, box_w, 18),
                align="center", halign="center",
                font_path=BOLD_FONT_PATH, autoscale=True)

        # Footer: IP (left) + version (right) — same pattern as other viewers
        # For leak screen readability, color uses text_color (synced with flash)
        footer_y = oy + area_h - footer_h - 2
        draw_aligned_text(draw=draw, text=disp_manager.ip_addr,
                          font_size=7, fill=text_color,
                          box=(box_x, footer_y, box_w, footer_h),
                          align="left", halign="center",
                          font_path=LIGHT_FONT_PATH)
        draw_aligned_text(draw=draw, text=disp_manager.version,
                          font_size=7, fill=text_color,
                          box=(box_x, footer_y, box_w, footer_h),
                          align="right", halign="center",
                          font_path=LIGHT_FONT_PATH)
