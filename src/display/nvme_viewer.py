import math
import time
from config import GRAPH_SIZE, FONT_PATH, BOLD_FONT_PATH
from base_viewer import BaseViewer
from draw_utils import draw_aligned_text, draw_multi_graph

PAGE_SIZE = 8
PAGE_INTERVAL = 3.0


class NvmeViewer(BaseViewer):
    def __init__(self, title, sensor_keys, colors, labels):
        super().__init__()
        self.title = title
        self.sensor_keys = sensor_keys
        self.colors = colors
        self.labels = labels

    def draw(self, draw, disp_manager, frame):
        offset = self._setup(draw, disp_manager)
        sensor_list = [disp_manager.sensors[k] for k in self.sensor_keys
                       if k in disp_manager.sensors]
        if not sensor_list:
            return

        n_data_pages = math.ceil(len(sensor_list) / PAGE_SIZE)
        total_pages = n_data_pages + 1
        page = int(time.time() / PAGE_INTERVAL) % total_pages

        graphbox, databox = self._boxes(offset, disp_manager.horizontal)
        gx1, gy1, gx2, gy2 = graphbox
        dx1, dy1, dx2, dy2 = databox
        footer_h = 12

        if page < n_data_pages:
            start = page * PAGE_SIZE
            end = min(start + PAGE_SIZE, len(sensor_list))
            page_sensors = sensor_list[start:end]
            page_labels = self.labels[start:end]
            page_colors = self.colors[start:end]

            has_data = any(len(s.buffer) >= 2 for s in page_sensors)
            if has_data:
                min_v, max_v, norm = self._normalize(page_sensors, gy2 - footer_h - gy1)
                self._draw_graph_labels(draw, min_v, max_v, '°C',
                                        gx1, gy1, gy2 - footer_h, GRAPH_SIZE)
                draw_multi_graph(draw, page_sensors, norm, page_colors,
                                 (gx1, gy1, gx2, gy2 - footer_h))

            page_title = f"{self.title}  [{page+1}/{n_data_pages}]"
            dw = dx2 - dx1
            self._draw_title(draw, page_title, dx1, dy1, dw, h=25)

            self._draw_sensor_rows(draw, page_sensors, page_labels, page_colors,
                                   dx1, dy1 + 25, dw, footer_h)
        else:
            self._draw_summary(draw, disp_manager, sensor_list,
                               graphbox, databox, footer_h)

        self._draw_footer(draw, disp_manager, gx1, gy2 - footer_h, GRAPH_SIZE, h=footer_h,
                          mode='left')
        self._draw_footer(draw, disp_manager, dx1, dy2 - footer_h, GRAPH_SIZE, h=footer_h,
                          mode='right')

    def _draw_sensor_rows(self, draw, sensors, labels, colors, dx1, start_y, dw, footer_h):
        num = len(sensors)
        cols = 1 if num <= 4 else 2
        rows_per_col = math.ceil(num / cols)
        avail_h = GRAPH_SIZE - 25 - footer_h - 4
        row_h = avail_h // rows_per_col
        col_w = dw // cols
        vf, lf, sq, uf = (14, 8, 5, 8) if row_h >= 18 else (10, 7, 4, 7)

        for i, (s, label, color) in enumerate(zip(sensors, labels, colors)):
            col = i // rows_per_col
            row = i % rows_per_col
            rx = dx1 + col * col_w
            ry = start_y + row * row_h
            sq_y = ry + (row_h - sq) // 2
            draw.rectangle((rx + 2, sq_y, rx + 2 + sq, sq_y + sq), fill=color)

            label_w = max(15, int(col_w * 0.35))
            unit_w = max(14, int(col_w * 0.20))
            sq_pad = sq + 4

            draw_aligned_text(draw=draw, text=label, font_size=lf, fill='white',
                              box=(rx + sq_pad, ry, label_w, row_h),
                              align="left", halign="center", font_path=FONT_PATH)

            if s.buffer:
                val_str = f"{s.buffer[-1]:.1f}"
                val_x = rx + sq_pad + label_w
                val_w = col_w - sq_pad - label_w - unit_w - 2

                draw_aligned_text(draw=draw, text=val_str, font_size=vf, fill=color,
                                  box=(val_x, ry, val_w, row_h),
                                  align="right", halign="center",
                                  font_path=BOLD_FONT_PATH, autoscale=True, ref_text="000.0")

                draw_aligned_text(draw=draw, text='°C', font_size=uf, fill='white',
                                  box=(val_x + val_w, ry, unit_w, row_h),
                                  align="left", halign="center", font_path=FONT_PATH)

    def _draw_summary(self, draw, disp_manager, sensors, graphbox, databox, footer_h):
        gx1, gy1, gx2, gy2 = graphbox
        dx1, dy1, dx2, dy2 = databox
        dw = dx2 - dx1

        vals = [(s.buffer[-1], self.labels[i]) for i, s in enumerate(sensors) if s.buffer]

        has_data = any(len(s.buffer) >= 2 for s in sensors)
        if has_data:
            min_v, max_v, norm = self._normalize(sensors, gy2 - footer_h - gy1)
            self._draw_graph_labels(draw, min_v, max_v, '°C',
                                    gx1, gy1, gy2 - footer_h, GRAPH_SIZE)
            draw_multi_graph(draw, sensors, norm, self.colors,
                             (gx1, gy1, gx2, gy2 - footer_h))

        self._draw_title(draw, f"{self.title}  [Summary]", dx1, dy1, dw, h=25)

        if not vals:
            return

        max_temp, max_label = max(vals, key=lambda x: x[0])
        avg_temp = sum(v for v, _ in vals) / len(vals)
        n = len(vals)

        rows = [
            ("MAX", f"{max_temp:.1f}°C", max_label),
            ("AVG", f"{avg_temp:.1f}°C", f"{n} drives"),
        ]
        row_h = (GRAPH_SIZE - 25 - footer_h - 4) // len(rows)

        for i, (label, val, sub) in enumerate(rows):
            y = dy1 + 25 + i * row_h

            draw_aligned_text(draw=draw, text=label, font_size=9, fill=(150, 150, 150),
                              box=(dx1 + 4, y, 28, row_h),
                              align="left", halign="center", font_path=FONT_PATH)

            draw_aligned_text(draw=draw, text=val, font_size=18, fill='white',
                              box=(dx1 + 34, y, dw - 38, row_h),
                              align="left", halign="center",
                              font_path=BOLD_FONT_PATH, autoscale=True)

            draw_aligned_text(draw=draw, text=sub, font_size=8, fill=(120, 120, 120),
                              box=(dx1 + 4, y + row_h - 14, dw - 8, 14),
                              align="right", halign="center", font_path=FONT_PATH)
