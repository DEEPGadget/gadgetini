import numpy as np

from config import (DEBUG, GRAPH_SIZE,
                    FONT_PATH, BOLD_FONT_PATH, EXTRABOLD_FONT_PATH,
                    LIGHT_FONT_PATH, THIN_FONT_PATH, ICON_FONT_PATH)
from draw_utils import draw_aligned_text, draw_graph


class SensorViewer:
    def __init__(self, title, sensor_key, sub1_key=None, sub2_key=None,
                 fixed_min=None, fixed_max=None,
                 sub1_autoscale=False, sub2_autoscale=False):
        self.title = title
        self.active = 1
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
            val_font, unit_font = 26, 15
            unit_w = 25

        display_val = val_str or f"{round(sub_data.buffer[-1], 2):.1f}"
        fill_color = err_color if val_str else 'white'
        draw_aligned_text(draw=draw, text=display_val, font_size=val_font, fill=fill_color,
                          box=(box_x, box_y + 15, box_w - unit_w, 30 if full_width else 24),
                          align="right", halign="top",
                          font_path=BOLD_FONT_PATH, autoscale=autoscale)

        # Unit
        if not val_str:
            draw_aligned_text(draw=draw, text=sub_data.unit_str, font_size=unit_font, fill='white',
                              box=(box_x + box_w - unit_w, box_y + 15, unit_w - 2, 30 if full_width else 24),
                              align="right", halign="top",
                              font_path=FONT_PATH, autoscale=False)

    def draw(self, draw, disp_manager, frame):
        if disp_manager.horizontal == 1:
            offset = (disp_manager.x_offset, disp_manager.y_offset)
        else:
            offset = (disp_manager.y_offset, disp_manager.x_offset)

        draw.rectangle((0, 0, disp_manager.width, disp_manager.height), fill='black')
        if DEBUG != 0:
            draw.rectangle((offset[0],offset[1],disp_manager.width, disp_manager.height), outline=(0,0,255), width=3)

        sensor_data = disp_manager.sensors[self.sensor_key]
        sub_sensor_data_1 = disp_manager.sensors[self.sub1_key] if self.sub1_key else None
        sub_sensor_data_2 = disp_manager.sensors[self.sub2_key] if self.sub2_key else None

        main_has_data = len(sensor_data.buffer) >= 2

        if not main_has_data and not sensor_data.error:
            print("Ready for reading the sensor data")
            return

        if main_has_data:
            if self.fixed_min is not None:
                min_value = self.fixed_min
                max_value = self.fixed_max
            else:
                min_value = int(np.min(sensor_data.buffer)*0.95)
                max_value = int(np.max(sensor_data.buffer)*1.05)

            normalized_data = np.interp(
                sensor_data.buffer,
                (min_value, max_value),
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

        err_color = (128, 128, 128)
        if main_has_data:
            sensor_value_str = str(f"{round(sensor_data.buffer[-1],2):.1f}")
            main_color = sensor_data.get_color_gradient(sensor_data.buffer[-1])
        else:
            sensor_value_str = "Err"
            main_color = err_color
        title = str(sensor_data.title_str)
        unit = str(sensor_data.unit_str) if main_has_data else ""

        if main_has_data:
            min_value_str = str(f"{round(min_value):.1f}"+sensor_data.unit_str)
            max_value_str = str(f"{round(max_value):.1f}"+sensor_data.unit_str)

        version_str = str(disp_manager.version)

        #TITLE
        draw_aligned_text(draw=draw, text=title, font_size=40, fill=main_color, box=(databox_x1, databox_y1, databox_x2-databox_x1, 30), align="center", halign="center", font_path=BOLD_FONT_PATH, autoscale=True)
        #VALUE
        draw_aligned_text(draw=draw, text=sensor_value_str, font_size=50, fill=main_color, box=(databox_x1, databox_y1+30, (databox_x2-databox_x1-25), 45), align="left", halign="center", font_path=EXTRABOLD_FONT_PATH, autoscale=False)
        #UNIT
        draw_aligned_text(draw=draw, text=unit, font_size=40, fill='white', box=(databox_x2-25, databox_y1+30, 25, 45), align="left", halign="top", font_path=BOLD_FONT_PATH, autoscale=True)

        #IP
        draw_aligned_text(draw=draw, text=disp_manager.ip_addr, font_size=8, fill='white', box=(databox_x1, databox_y2-12, GRAPH_SIZE, 12), align="left", halign="center", font_path=LIGHT_FONT_PATH)

        #Gadgetini Version
        draw_aligned_text(draw=draw, text=version_str, font_size=8, fill='gray', box=(databox_x1, databox_y2-12, GRAPH_SIZE, 12), align="right", halign="center", font_path=LIGHT_FONT_PATH)


        margin = 5
        dw = databox_x2 - databox_x1
        sub_count = (1 if sub_sensor_data_1 else 0) + (1 if sub_sensor_data_2 else 0)

        if sub_count == 2:
            # Two subs — each gets half width
            half_w = dw / 2 - margin
            if sub_sensor_data_1:
                self._draw_sub(draw, sub_sensor_data_1,
                               databox_x1, half_w, databox_y1 + 75,
                               err_color, self.sub1_autoscale)
            if sub_sensor_data_2:
                self._draw_sub(draw, sub_sensor_data_2,
                               databox_x1 + dw / 2 + margin, half_w, databox_y1 + 75,
                               err_color, self.sub2_autoscale)
        elif sub_count == 1:
            # One sub — full width, centered
            sub = sub_sensor_data_1 or sub_sensor_data_2
            autoscale = self.sub1_autoscale if sub_sensor_data_1 else self.sub2_autoscale
            self._draw_sub(draw, sub,
                           databox_x1, dw, databox_y1 + 75,
                           err_color, autoscale, full_width=True)

        #Min/Max & Graph
        if main_has_data:
            draw_aligned_text(draw=draw, text=max_value_str, font_size=8, fill=sensor_data.get_color_gradient(max_value), box=(graphbox_x1, graphbox_y1, GRAPH_SIZE, 8), align="center", halign="top", font_path=FONT_PATH)
            draw_aligned_text(draw=draw, text=min_value_str, font_size=8, fill=sensor_data.get_color_gradient(min_value), box=(graphbox_x1, graphbox_y2-8, GRAPH_SIZE, 8), align="center", halign="bottom", font_path=FONT_PATH)

            draw_graph(draw, sensor_data, normalized_data,
                       (graphbox_x1, graphbox_y1, graphbox_x2, graphbox_y2))
