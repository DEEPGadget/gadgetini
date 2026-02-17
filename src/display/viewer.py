import numpy as np

from config import (DEBUG, GRAPH_SIZE,
                    FONT_PATH, BOLD_FONT_PATH, EXTRABOLD_FONT_PATH,
                    LIGHT_FONT_PATH, THIN_FONT_PATH)
from draw_utils import draw_aligned_text


class SensorViewer:
    def __init__(self, title, sensor_key, sub1_key, sub2_key,
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

    def draw(self, draw, disp_manager, frame):
        if disp_manager.horizontal == 1:
            offset = (disp_manager.x_offset, disp_manager.y_offset)
        else:
            offset = (disp_manager.y_offset, disp_manager.x_offset)

        draw.rectangle((0, 0, disp_manager.width, disp_manager.height), fill='black')
        if DEBUG != 0:
            draw.rectangle((offset[0],offset[1],disp_manager.width, disp_manager.height), outline=(0,0,255), width=3)

        sensor_data = disp_manager.sensors[self.sensor_key]
        sub_sensor_data_1 = disp_manager.sensors[self.sub1_key]
        sub_sensor_data_2 = disp_manager.sensors[self.sub2_key]

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
        draw_aligned_text(draw=draw, text=sensor_value_str, font_size=50, fill=main_color, box=(databox_x1, databox_y1+30, (databox_x2-databox_x1-25), 45), align="right", halign="top", font_path=EXTRABOLD_FONT_PATH)
        #UNIT
        draw_aligned_text(draw=draw, text=unit, font_size=40, fill='white', box=(databox_x2-25, databox_y1+30, 25, 45), align="left", halign="top", font_path=BOLD_FONT_PATH, autoscale=True)

        #IP
        draw_aligned_text(draw=draw, text=disp_manager.ip_addr, font_size=8, fill='white', box=(databox_x1, databox_y2-12, GRAPH_SIZE, 12), align="left", halign="center", font_path=LIGHT_FONT_PATH)

        #Gadgetini Version
        draw_aligned_text(draw=draw, text=version_str, font_size=8, fill='gray', box=(databox_x1, databox_y2-12, GRAPH_SIZE, 12), align="right", halign="center", font_path=LIGHT_FONT_PATH)


        margin=5
        #Sub sensor 1
        sub1_val_str = "Err" if sub_sensor_data_1.error and len(sub_sensor_data_1.buffer) == 0 else None
        if len(sub_sensor_data_1.buffer) > 0 or sub1_val_str:
            draw_aligned_text(draw=draw, text=sub_sensor_data_1.title_str, font_size=6, fill='white', box=(databox_x1, databox_y1+75, (databox_x2-databox_x1)/2-margin, 15), align="center", halign="center", font_path=THIN_FONT_PATH, autoscale=False)
            draw_aligned_text(draw=draw, text=sub1_val_str or str(f"{round(sub_sensor_data_1.buffer[-1],2):.1f}"), font_size=26, fill=err_color if sub1_val_str else 'white', box=(databox_x1, databox_y1+90, (databox_x2-databox_x1)/2-margin, 24), align="right", halign="top", font_path=BOLD_FONT_PATH, autoscale=self.sub1_autoscale)
            if not sub1_val_str:
                draw_aligned_text(draw=draw, text=sub_sensor_data_1.unit_str, font_size=15, fill='white', box=(databox_x1+(databox_x2-databox_x1)/2-25, databox_y1+115, 25-2-margin, 15), align="right", halign="top", font_path=FONT_PATH, autoscale=False)


        sub2_val_str = "Err" if sub_sensor_data_2.error and len(sub_sensor_data_2.buffer) == 0 else None
        if len(sub_sensor_data_2.buffer) > 0 or sub2_val_str:
            draw_aligned_text(draw=draw, text=sub_sensor_data_2.title_str, font_size=6, fill='white', box=(databox_x1+(databox_x2-databox_x1)/2+margin, databox_y1+75, (databox_x2-databox_x1)/2-margin, 15), align="center", halign="center", font_path=THIN_FONT_PATH, autoscale=False)
            draw_aligned_text(draw=draw, text=sub2_val_str or str(f"{round(sub_sensor_data_2.buffer[-1],2):.1f}"), font_size=26, fill=err_color if sub2_val_str else 'white', box=(databox_x1+(databox_x2-databox_x1)/2+margin, databox_y1+90, (databox_x2-databox_x1)/2-margin, 24), align="right", halign="top", font_path=BOLD_FONT_PATH, autoscale=self.sub2_autoscale)
            if not sub2_val_str:
                draw_aligned_text(draw=draw, text=sub_sensor_data_2.unit_str, font_size=15, fill='white', box=(databox_x1+(databox_x2-databox_x1)-25+margin, databox_y1+115, 25-2-margin, 15), align="right", halign="top", font_path=FONT_PATH, autoscale=False)


        #Min/Max & Graph
        if main_has_data:
            draw_aligned_text(draw=draw, text=max_value_str, font_size=8, fill=sensor_data.get_color_gradient(max_value), box=(graphbox_x1, graphbox_y1, GRAPH_SIZE, 8), align="center", halign="top", font_path=FONT_PATH)
            draw_aligned_text(draw=draw, text=min_value_str, font_size=8, fill=sensor_data.get_color_gradient(min_value), box=(graphbox_x1, graphbox_y2-8, GRAPH_SIZE, 8), align="center", halign="bottom", font_path=FONT_PATH)

            for i in range(1, len(sensor_data.buffer)):
                px1 = i + graphbox_x1
                py1 = int(graphbox_y2 - normalized_data[i-1])
                px2 = i + graphbox_x1 + 1
                py2 = int(graphbox_y2 - normalized_data[i])
                color = sensor_data.get_color_gradient(sensor_data.buffer[i])
                draw.line((px1,py1,px2,py2), fill=color, width=3)
