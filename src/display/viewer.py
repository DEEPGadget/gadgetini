import numpy as np

from config import (DEBUG, GRAPH_SIZE,
                    FONT_PATH, BOLD_FONT_PATH, EXTRABOLD_FONT_PATH,
                    LIGHT_FONT_PATH, THIN_FONT_PATH, ICON_FONT_PATH)
from base_viewer import BaseViewer
from draw_utils import draw_aligned_text, draw_graph


class SensorViewer(BaseViewer):
    def __init__(self, title, sensor_key, sub1_key=None, sub2_key=None,
                 fixed_min=None, fixed_max=None,
                 sub1_autoscale=False, sub2_autoscale=False):
        super().__init__()
        self.title = title
        self.sensor_key = sensor_key
        self.sub1_key = sub1_key
        self.sub2_key = sub2_key
        self.fixed_min = fixed_min
        self.fixed_max = fixed_max
        self.sub1_autoscale = sub1_autoscale
        self.sub2_autoscale = sub2_autoscale

    def _draw_sub(self, draw, sub_data, box_x, box_w, box_y,
                  err_color, autoscale, full_width=False):
        """Draw a single sub sensor (icon/label + value + unit)."""
        val_str = "Err" if sub_data.error and len(sub_data.buffer) == 0 else None
        if len(sub_data.buffer) == 0 and not val_str:
            return

        # Icon / Label
        if sub_data.icon and sub_data.label:
            icon_w = 16
            draw_aligned_text(draw=draw, text=sub_data.icon, font_size=12, fill='white',
                              box=(box_x, box_y, icon_w, 15),
                              align="center", halign="center", font_path=ICON_FONT_PATH)
            draw_aligned_text(draw=draw, text=sub_data.label, font_size=9, fill='white',
                              box=(box_x + icon_w, box_y, box_w - icon_w, 15),
                              align="center", halign="center", font_path=FONT_PATH)
        elif sub_data.icon:
            draw_aligned_text(draw=draw, text=sub_data.icon, font_size=14, fill='white',
                              box=(box_x, box_y, box_w, 15),
                              align="center", halign="center",
                              font_path=ICON_FONT_PATH, autoscale=False)
        else:
            text = sub_data.label or sub_data.title_str
            draw_aligned_text(draw=draw, text=text, font_size=6, fill='white',
                              box=(box_x, box_y, box_w, 15),
                              align="center", halign="center",
                              font_path=THIN_FONT_PATH, autoscale=False)

        # Value
        if full_width:
            val_font, unit_font = 36, 20
            unit_w = 30
        else:
            val_font, unit_font = 18, 12
            unit_w = 20

        display_val = val_str or f"{round(sub_data.buffer[-1], 2):.1f}"
        fill_color = err_color if val_str else 'white'
        draw_aligned_text(draw=draw, text=display_val, font_size=val_font, fill=fill_color,
                          box=(box_x, box_y + 15, box_w - unit_w, 30 if full_width else 24),
                          align="right", halign="top",
                          font_path=BOLD_FONT_PATH, autoscale=True, ref_text="000.0")

        # Unit
        if not val_str:
            draw_aligned_text(draw=draw, text=sub_data.unit_str, font_size=unit_font, fill='white',
                              box=(box_x + box_w - unit_w, box_y + 15, unit_w - 2, 30 if full_width else 24),
                              align="right", halign="top",
                              font_path=FONT_PATH, autoscale=False)

    def draw(self, draw, disp_manager, frame):
        offset = self._setup(draw, disp_manager)

        sensor_data = disp_manager.sensors[self.sensor_key]
        sub_sensor_data_1 = disp_manager.sensors[self.sub1_key] if self.sub1_key else None
        sub_sensor_data_2 = disp_manager.sensors[self.sub2_key] if self.sub2_key else None

        main_has_data = len(sensor_data.buffer) >= 2

        if not main_has_data and not sensor_data.error:
            return

        if main_has_data:
            min_value, max_value, normalized_data = self._normalize_single(
                sensor_data, GRAPH_SIZE, self.fixed_min, self.fixed_max)

        gray = (50, 50, 50)
        graphbox, databox = self._boxes(offset, disp_manager.horizontal)
        gx1, gy1, gx2, gy2 = graphbox
        dx1, dy1, dx2, dy2 = databox

        if DEBUG == 1:
            draw.rectangle(graphbox, outline=gray, width=3)
            draw.rectangle(databox, outline=gray, width=3)

        err_color = self.ERR_COLOR
        if main_has_data:
            sensor_value_str = f"{round(sensor_data.buffer[-1], 2):.1f}"
            main_color = sensor_data.get_color_gradient(sensor_data.buffer[-1])
        else:
            sensor_value_str = "Err"
            main_color = err_color
        title = sensor_data.title_str
        unit = sensor_data.unit_str if main_has_data else ""

        dw = dx2 - dx1

        # TITLE
        self._draw_title(draw, title, dx1, dy1, dw, h=30)

        # VALUE
        draw_aligned_text(draw=draw, text=sensor_value_str, font_size=50, fill=main_color,
                          box=(dx1, dy1 + 30, dw - 25, 45),
                          align="left", halign="center",
                          font_path=EXTRABOLD_FONT_PATH, autoscale=False)
        # UNIT
        draw_aligned_text(draw=draw, text=unit, font_size=40, fill='white',
                          box=(dx2 - 25, dy1 + 30, 25, 45),
                          align="left", halign="top",
                          font_path=BOLD_FONT_PATH, autoscale=True)

        # FOOTER
        self._draw_footer(draw, disp_manager, dx1, dy2 - 12, GRAPH_SIZE, h=12)

        # SUBS
        margin = 5
        sub_count = (1 if sub_sensor_data_1 else 0) + (1 if sub_sensor_data_2 else 0)

        if sub_count == 2:
            half_w = dw / 2 - margin
            if sub_sensor_data_1:
                self._draw_sub(draw, sub_sensor_data_1,
                               dx1, half_w, dy1 + 75,
                               err_color, self.sub1_autoscale)
            if sub_sensor_data_2:
                self._draw_sub(draw, sub_sensor_data_2,
                               dx1 + dw / 2 + margin, half_w, dy1 + 75,
                               err_color, self.sub2_autoscale)
        elif sub_count == 1:
            sub = sub_sensor_data_1 or sub_sensor_data_2
            autoscale = self.sub1_autoscale if sub_sensor_data_1 else self.sub2_autoscale
            self._draw_sub(draw, sub,
                           dx1, dw, dy1 + 75,
                           err_color, autoscale, full_width=True)

        # Min/Max & Graph
        if main_has_data:
            self._draw_graph_labels(
                draw, min_value, max_value, sensor_data.unit_str,
                gx1, gy1, gy2, GRAPH_SIZE,
                min_fill=sensor_data.get_color_gradient(min_value),
                max_fill=sensor_data.get_color_gradient(max_value))

            draw_graph(draw, sensor_data, normalized_data, graphbox)
