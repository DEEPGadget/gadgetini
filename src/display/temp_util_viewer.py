from config import (DEBUG, GRAPH_SIZE, FONT_PATH, BOLD_FONT_PATH)
from base_viewer import BaseViewer
from draw_utils import draw_aligned_text, draw_multi_graph


class TempUtilViewer(BaseViewer):
    """Dual multi-graph: temperature (left) + utilization/power (right) + legend."""

    def __init__(self, temp_title, util_title,
                 sensor_keys, colors, labels, util_keys):
        super().__init__()
        self.temp_title = temp_title
        self.util_title = util_title
        self.sensor_keys = sensor_keys
        self.colors = colors
        self.labels = labels
        self.util_keys = util_keys

    def draw(self, draw, disp_manager, frame):
        offset = self._setup(draw, disp_manager)

        sensor_list = [disp_manager.sensors[k] for k in self.sensor_keys]
        util_list = [disp_manager.sensors[k] for k in self.util_keys]
        num = len(sensor_list)

        has_temp = any(len(s.buffer) >= 2 for s in sensor_list)
        has_util = any(len(s.buffer) >= 2 for s in util_list)
        any_error = (any(s.error for s in sensor_list) or
                     any(s.error for s in util_list))

        if not has_temp and not has_util and not any_error:
            return

        # Layout
        title_h = 15
        graph_h = 95
        footer_h = 12
        legend_h = GRAPH_SIZE - title_h - graph_h - footer_h

        if disp_manager.horizontal == 1:
            lx = offset[0]
            rx = offset[0] + GRAPH_SIZE + 5
            base_y = offset[1]
            full_w = GRAPH_SIZE * 2 + 5
        else:
            lx = offset[0]
            rx = offset[0]
            base_y = offset[1]
            full_w = GRAPH_SIZE

        # === LEFT: Temperature multi-graph ===
        self._draw_title(draw, self.temp_title, lx, base_y, GRAPH_SIZE, h=title_h)

        gx1, gy1 = lx, base_y + title_h
        gx2, gy2 = lx + GRAPH_SIZE, gy1 + graph_h

        if DEBUG == 1:
            draw.rectangle((gx1, gy1, gx2, gy2), outline=(50, 50, 50), width=1)

        if has_temp:
            min_val, max_val, norm_list = self._normalize(sensor_list, graph_h)
            self._draw_graph_labels(draw, min_val, max_val,
                                    sensor_list[0].unit_str,
                                    gx1, gy1, gy2, GRAPH_SIZE, font_size=7)
            draw_multi_graph(draw, sensor_list, norm_list, self.colors,
                             (gx1, gy1, gx2, gy2))

        # === RIGHT: Utilization/Power multi-graph ===
        self._draw_title(draw, self.util_title, rx, base_y, GRAPH_SIZE, h=title_h)

        ux1, uy1 = rx, base_y + title_h
        ux2, uy2 = rx + GRAPH_SIZE, uy1 + graph_h

        if DEBUG == 1:
            draw.rectangle((ux1, uy1, ux2, uy2), outline=(50, 50, 50), width=1)

        if has_util:
            u_min, u_max, u_norm = self._normalize(util_list, graph_h)
            self._draw_graph_labels(draw, u_min, u_max,
                                    util_list[0].unit_str,
                                    ux1, uy1, uy2, GRAPH_SIZE, font_size=7)
            draw_multi_graph(draw, util_list, u_norm, self.colors,
                             (ux1, uy1, ux2, uy2))

        # === LEGEND (full width, below both graphs) ===
        legend_y = base_y + title_h + graph_h

        if num <= 4:
            cols = num
        else:
            cols = 4
        rows = (num + cols - 1) // cols
        row_h_l = min(14, legend_h // max(rows, 1))
        col_w = full_w // max(cols, 1)

        for i, (s, label, color) in enumerate(
                zip(sensor_list, self.labels, self.colors)):
            col = i % cols
            row = i // cols
            cx = lx + col * col_w
            cy = legend_y + row * row_h_l
            self._draw_legend_row(draw, s, label, color, cx, cy, row_h_l, col_w)

        # FOOTERS
        ft_y = base_y + GRAPH_SIZE - footer_h
        if disp_manager.horizontal == 1:
            self._draw_footer(draw, disp_manager, lx, ft_y, GRAPH_SIZE, h=footer_h,
                              mode='left')
            self._draw_footer(draw, disp_manager, rx, ft_y, GRAPH_SIZE, h=footer_h,
                              mode='right')
        else:
            self._draw_footer(draw, disp_manager, lx, ft_y, full_w, h=footer_h)
