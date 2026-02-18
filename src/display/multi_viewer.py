import numpy as np

from config import (DEBUG, GRAPH_SIZE,
                    FONT_PATH, BOLD_FONT_PATH,
                    LIGHT_FONT_PATH)
from draw_utils import draw_aligned_text, draw_multi_graph


class MultiSensorViewer:
    def __init__(self, title, sensor_keys, colors, labels):
        self.title = title
        self.active = 1
        self.sensor_keys = sensor_keys
        self.colors = colors
        self.labels = labels

    def draw(self, draw, disp_manager, frame):
        if disp_manager.horizontal == 1:
            offset = (disp_manager.x_offset, disp_manager.y_offset)
        else:
            offset = (disp_manager.y_offset, disp_manager.x_offset)

        draw.rectangle((0, 0, disp_manager.width, disp_manager.height), fill='black')
        if DEBUG != 0:
            draw.rectangle((offset[0], offset[1], disp_manager.width, disp_manager.height),
                           outline=(0, 0, 255), width=3)

        sensor_list = [disp_manager.sensors[k] for k in self.sensor_keys]
        num = len(sensor_list)

        has_data = any(len(s.buffer) >= 2 for s in sensor_list)
        any_error = any(s.error for s in sensor_list)

        # Still waiting for initial data — nothing to show yet
        if not has_data and not any_error:
            return

        # GRAPHBOX
        gx1 = offset[0]
        gy1 = offset[1]
        gx2 = gx1 + GRAPH_SIZE
        gy2 = gy1 + GRAPH_SIZE

        # DATABOX
        if disp_manager.horizontal == 1:
            dx1 = gx2 + 5
            dy1 = gy1
        else:
            dx1 = gx1
            dy1 = gy2 + 5
        dx2 = dx1 + GRAPH_SIZE
        dy2 = dy1 + GRAPH_SIZE

        if DEBUG == 1:
            gray = (50, 50, 50)
            draw.rectangle((gx1, gy1, gx2, gy2), outline=gray, width=3)
            draw.rectangle((dx1, dy1, dx2, dy2), outline=gray, width=3)

        unit_str = sensor_list[0].unit_str

        # Graph — only when we have plottable data
        if has_data:
            all_values = []
            for s in sensor_list:
                if len(s.buffer) > 0:
                    all_values.extend(s.buffer)

            min_value = int(np.min(all_values) * 0.95)
            max_value = int(np.max(all_values) * 1.05)
            if min_value == max_value:
                max_value = min_value + 1

            normalized_list = []
            for s in sensor_list:
                if len(s.buffer) >= 2:
                    norm = np.interp(s.buffer, (min_value, max_value), (8, GRAPH_SIZE - 8))
                else:
                    norm = np.array([])
                normalized_list.append(norm)

            min_str = f"{round(min_value):.1f}{unit_str}"
            max_str = f"{round(max_value):.1f}{unit_str}"

            draw_aligned_text(draw=draw, text=max_str, font_size=8, fill='white',
                              box=(gx1, gy1, GRAPH_SIZE, 8),
                              align="center", halign="top", font_path=FONT_PATH)
            draw_aligned_text(draw=draw, text=min_str, font_size=8, fill='white',
                              box=(gx1, gy2 - 8, GRAPH_SIZE, 8),
                              align="center", halign="bottom", font_path=FONT_PATH)

            draw_multi_graph(draw, sensor_list, normalized_list, self.colors,
                             (gx1, gy1, gx2, gy2))

        # === Data panel layout (adaptive) ===
        dw = dx2 - dx1
        footer_h = 12

        if num <= 5:
            cols = 1
#            title_h = 25
        else:
            cols = 2
#            title_h = 16
        title_h = 25


        rows_per_col = (num + cols - 1) // cols
        start_y = dy1 + title_h + 2
        avail_h = GRAPH_SIZE - title_h - footer_h - 4
        row_h = avail_h // rows_per_col
        col_w = dw // cols


        # Font sizing based on row height
        if row_h >= 24:
            vf, lf, sq, uf = 20, 10, 6, 10
        elif row_h >= 18:
            vf, lf, sq, uf = 14, 8, 5, 8
        else:
            vf, lf, sq, uf = 10, 7, 4, 7


        #print(f"row_h = {row_h}, vf = {vf}, lf = {lf}")

        # TITLE
        draw_aligned_text(draw=draw, text=self.title, font_size=15, fill='white',
                          box=(dx1, dy1, dw, title_h),
                          align="center", halign="bottom",
                          font_path=BOLD_FONT_PATH, autoscale=False)

        # Sensor value rows
        err_color = (128, 128, 128)
        label_w = max(15, int(col_w * 0.22))
        unit_w = max(14, int(col_w * 0.20))
        sq_pad = sq + 4

        for i, (s, label, color) in enumerate(zip(sensor_list, self.labels, self.colors)):
            col = i // rows_per_col
            row = i % rows_per_col
            rx = dx1 + col * col_w
            ry = start_y + row * row_h

            # Color square
            sq_y = ry + (row_h - sq) // 2
            draw.rectangle((rx + 2, sq_y, rx + 2 + sq, sq_y + sq), fill=color)

            # Label
            draw_aligned_text(draw=draw, text=label, font_size=lf, fill='white',
                              box=(rx + sq_pad, ry, label_w, row_h),
                              align="left", halign="center", font_path=FONT_PATH)

            # Value + Unit
            if len(s.buffer) > 0:
                val_str = f"{s.buffer[-1]:.1f}"
                val_color = color
            elif s.error:
                val_str = "Err"
                val_color = err_color
            else:
                continue

            val_x = rx + sq_pad + label_w
            val_w = col_w - sq_pad - label_w - unit_w - 2

            draw_aligned_text(draw=draw, text=val_str, font_size=vf, fill=val_color,
                              box=(val_x, ry, val_w, row_h),
                              align="right", halign="center", font_path=BOLD_FONT_PATH, autoscale=True)
            if len(s.buffer) > 0:
                draw_aligned_text(draw=draw, text=unit_str, font_size=uf, fill='white',
                                  box=(val_x + val_w, ry, unit_w, row_h),
                                  align="left", halign="center", font_path=FONT_PATH)

        # IP
        draw_aligned_text(draw=draw, text=disp_manager.ip_addr, font_size=8, fill='white',
                          box=(dx1, dy2 - footer_h, GRAPH_SIZE, footer_h),
                          align="left", halign="center", font_path=LIGHT_FONT_PATH)

        # Version
        draw_aligned_text(draw=draw, text=disp_manager.version, font_size=8, fill='gray',
                          box=(dx1, dy2 - footer_h, GRAPH_SIZE, footer_h),
                          align="right", halign="center", font_path=LIGHT_FONT_PATH)
