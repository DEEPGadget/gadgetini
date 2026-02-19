from config import (DEBUG, GRAPH_SIZE,
                    FONT_PATH, BOLD_FONT_PATH)
from base_viewer import BaseViewer
from draw_utils import draw_aligned_text, draw_multi_graph


class MultiSensorViewer(BaseViewer):
    def __init__(self, title, sensor_keys, colors, labels):
        super().__init__()
        self.title = title
        self.sensor_keys = sensor_keys
        self.colors = colors
        self.labels = labels

    def draw(self, draw, disp_manager, frame):
        offset = self._setup(draw, disp_manager)

        sensor_list = [disp_manager.sensors[k] for k in self.sensor_keys]
        num = len(sensor_list)

        has_data = any(len(s.buffer) >= 2 for s in sensor_list)
        any_error = any(s.error for s in sensor_list)

        if not has_data and not any_error:
            return

        graphbox, databox = self._boxes(offset, disp_manager.horizontal)
        gx1, gy1, gx2, gy2 = graphbox
        dx1, dy1, dx2, dy2 = databox

        footer_h = 12
        graph_gy2 = gy2 - footer_h
        actual_graph_h = graph_gy2 - gy1

        if DEBUG == 1:
            gray = (50, 50, 50)
            draw.rectangle((gx1, gy1, gx2, graph_gy2), outline=gray, width=3)
            draw.rectangle(databox, outline=gray, width=3)

        unit_str = sensor_list[0].unit_str

        # Graph
        if has_data:
            min_val, max_val, normalized_list = self._normalize(sensor_list, actual_graph_h)
            self._draw_graph_labels(draw, min_val, max_val, unit_str,
                                    gx1, gy1, graph_gy2, GRAPH_SIZE)
            draw_multi_graph(draw, sensor_list, normalized_list, self.colors,
                             (gx1, gy1, gx2, graph_gy2))

        # === Data panel layout ===
        dw = dx2 - dx1

        if num <= 5:
            cols = 1
        else:
            cols = 2
        title_h = 25

        rows_per_col = (num + cols - 1) // cols
        start_y = dy1 + title_h + 2
        avail_h = GRAPH_SIZE - title_h - footer_h - 4
        row_h = avail_h // rows_per_col
        col_w = dw // cols

        # Font sizing based on row height and column count
        if cols == 2:
            if row_h >= 18:
                vf, lf, sq, uf = 14, 8, 5, 8
            else:
                vf, lf, sq, uf = 10, 7, 4, 7
        elif row_h >= 24:
            vf, lf, sq, uf = 20, 10, 6, 10
        elif row_h >= 18:
            vf, lf, sq, uf = 14, 8, 5, 8
        else:
            vf, lf, sq, uf = 10, 7, 4, 7

        # TITLE
        self._draw_title(draw, self.title, dx1, dy1, dw, h=title_h)

        # Sensor value rows
        label_w = max(15, int(col_w * 0.22))
        unit_w = max(14, int(col_w * 0.20))
        sq_pad = sq + 4

        for i, (s, label, color) in enumerate(zip(sensor_list, self.labels, self.colors)):
            col = i // rows_per_col
            row = i % rows_per_col
            rx = dx1 + col * col_w
            ry = start_y + row * row_h

            sq_y = ry + (row_h - sq) // 2
            draw.rectangle((rx + 2, sq_y, rx + 2 + sq, sq_y + sq), fill=color)

            draw_aligned_text(draw=draw, text=label, font_size=lf, fill='white',
                              box=(rx + sq_pad, ry, label_w, row_h),
                              align="left", halign="center", font_path=FONT_PATH)

            if len(s.buffer) > 0:
                val_str = f"{s.buffer[-1]:.1f}"
                val_color = color
            elif s.error:
                val_str = "Err"
                val_color = self.ERR_COLOR
            else:
                continue

            val_x = rx + sq_pad + label_w
            val_w = col_w - sq_pad - label_w - unit_w - 2

            draw_aligned_text(draw=draw, text=val_str, font_size=vf, fill=val_color,
                              box=(val_x, ry, val_w, row_h),
                              align="right", halign="center",
                              font_path=BOLD_FONT_PATH, autoscale=True, ref_text="000.0")
            if len(s.buffer) > 0:
                draw_aligned_text(draw=draw, text=unit_str, font_size=uf, fill='white',
                                  box=(val_x + val_w, ry, unit_w, row_h),
                                  align="left", halign="center", font_path=FONT_PATH)

        # FOOTERS
        self._draw_footer(draw, disp_manager, gx1, graph_gy2, GRAPH_SIZE, h=footer_h,
                          mode='left')
        self._draw_footer(draw, disp_manager, dx1, dy2 - footer_h, GRAPH_SIZE, h=footer_h,
                          mode='right')

