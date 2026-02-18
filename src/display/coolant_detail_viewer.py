from config import (DEBUG, GRAPH_SIZE, FONT_PATH, BOLD_FONT_PATH)
from base_viewer import BaseViewer
from draw_utils import draw_aligned_text, draw_multi_graph


class CoolantDetailViewer(BaseViewer):
    """Side-by-side dual coolant loop viewer with individual graphs and delta-T."""

    def __init__(self, loops):
        """
        loops: list of dicts, each with:
            'title': str
            'sensor_keys': [inlet_key, outlet_key]
            'delta_key': str
            'colors': [inlet_color, outlet_color]
            'labels': [inlet_label, outlet_label]
        """
        super().__init__()
        self.loops = loops

    def draw(self, draw, disp_manager, frame):
        offset = self._setup(draw, disp_manager)

        for pi, loop in enumerate(self.loops):
            if disp_manager.horizontal == 1:
                px = offset[0] + pi * (GRAPH_SIZE + 5)
                py = offset[1]
            else:
                px = offset[0]
                py = offset[1] + pi * (GRAPH_SIZE + 5)

            self._draw_panel(draw, disp_manager, loop, px, py, pi)

    def _draw_panel(self, draw, disp_manager, loop, px, py, panel_idx):
        w = GRAPH_SIZE
        title_h = 15
        graph_h = 78
        row_h = 15
        delta_h = 12
        footer_h = 10

        sensors = [disp_manager.sensors[k] for k in loop['sensor_keys']]
        delta_sensor = disp_manager.sensors[loop['delta_key']]
        colors = loop['colors']
        labels = loop['labels']

        has_data = any(len(s.buffer) >= 2 for s in sensors)
        any_error = any(s.error for s in sensors)

        if not has_data and not any_error:
            return

        self._draw_title(draw, loop['title'], px, py, w, h=title_h)

        gx1, gy1 = px, py + title_h
        gx2, gy2 = px + w, gy1 + graph_h

        if DEBUG == 1:
            draw.rectangle((gx1, gy1, gx2, gy2), outline=(50, 50, 50), width=1)

        if has_data:
            min_val, max_val, normalized_list = self._normalize(sensors, graph_h)
            self._draw_graph_labels(draw, min_val, max_val, sensors[0].unit_str,
                                    gx1, gy1, gy2, w, font_size=7)
            draw_multi_graph(draw, sensors, normalized_list, colors,
                             (gx1, gy1, gx2, gy2))

        # Value rows
        vy = gy2
        sq = 5
        sq_pad = sq + 3
        label_w = 25
        unit_w = 18
        val_w = w - sq_pad - label_w - unit_w - 2

        for i, (s, label, color) in enumerate(zip(sensors, labels, colors)):
            ry = vy + i * row_h

            sq_y = ry + (row_h - sq) // 2
            draw.rectangle((px + 2, sq_y, px + 2 + sq, sq_y + sq), fill=color)

            draw_aligned_text(draw=draw, text=label, font_size=9, fill='white',
                              box=(px + sq_pad, ry, label_w, row_h),
                              align="left", halign="center", font_path=FONT_PATH)

            if len(s.buffer) > 0:
                val_str = f"{s.buffer[-1]:.1f}"
                val_color = color
            elif s.error:
                val_str = "Err"
                val_color = self.ERR_COLOR
            else:
                continue

            val_x = px + sq_pad + label_w
            draw_aligned_text(draw=draw, text=val_str, font_size=14, fill=val_color,
                              box=(val_x, ry, val_w, row_h),
                              align="right", halign="center",
                              font_path=BOLD_FONT_PATH, autoscale=True, ref_text="000.0")
            if len(s.buffer) > 0:
                draw_aligned_text(draw=draw, text=s.unit_str, font_size=9, fill='white',
                                  box=(val_x + val_w, ry, unit_w, row_h),
                                  align="left", halign="center", font_path=FONT_PATH)

        # Delta-T row
        dt_y = vy + len(sensors) * row_h
        if len(delta_sensor.buffer) > 0:
            dt_val = f"\u0394T {delta_sensor.buffer[-1]:.1f}{delta_sensor.unit_str}"
            draw_aligned_text(draw=draw, text=dt_val, font_size=11, fill=(200, 200, 200),
                              box=(px, dt_y, w, delta_h),
                              align="center", halign="center",
                              font_path=BOLD_FONT_PATH, autoscale=True)
        elif delta_sensor.error:
            draw_aligned_text(draw=draw, text="\u0394T Err", font_size=11,
                              fill=self.ERR_COLOR,
                              box=(px, dt_y, w, delta_h),
                              align="center", halign="center",
                              font_path=BOLD_FONT_PATH)

        # Footer
        ft_y = py + GRAPH_SIZE - footer_h
        mode = 'left' if panel_idx == 0 else 'right'
        self._draw_footer(draw, disp_manager, px, ft_y, w, h=footer_h, mode=mode)
