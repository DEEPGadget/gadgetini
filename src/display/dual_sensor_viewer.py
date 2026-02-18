from config import (DEBUG, GRAPH_SIZE, FONT_PATH, BOLD_FONT_PATH)
from base_viewer import BaseViewer
from draw_utils import draw_aligned_text, draw_graph


class DualSensorViewer(BaseViewer):
    """Two independent sensor graphs displayed side by side."""

    def __init__(self, panels):
        """
        panels: list of 2 dicts, each with:
            'title': str
            'sensor_key': str
        """
        super().__init__()
        self.panels = panels

    def draw(self, draw, disp_manager, frame):
        offset = self._setup(draw, disp_manager)

        for pi, panel in enumerate(self.panels):
            if disp_manager.horizontal == 1:
                px = offset[0] + pi * (GRAPH_SIZE + 5)
                py = offset[1]
            else:
                px = offset[0]
                py = offset[1] + pi * (GRAPH_SIZE + 5)

            self._draw_panel(draw, disp_manager, panel, px, py, pi)

    def _draw_panel(self, draw, disp_manager, panel, px, py, panel_idx):
        w = GRAPH_SIZE
        title_h = 15
        graph_h = 90
        value_h = 30
        footer_h = 10

        sensor = disp_manager.sensors[panel['sensor_key']]
        has_data = len(sensor.buffer) >= 2

        if not has_data and not sensor.error:
            return

        self._draw_title(draw, panel['title'], px, py, w, h=title_h)

        gx1, gy1 = px, py + title_h
        gx2, gy2 = px + w, gy1 + graph_h

        if DEBUG == 1:
            draw.rectangle((gx1, gy1, gx2, gy2), outline=(50, 50, 50), width=1)

        if has_data:
            min_val, max_val, normalized = self._normalize_single(sensor, graph_h)
            self._draw_graph_labels(draw, min_val, max_val, sensor.unit_str,
                                    gx1, gy1, gy2, w, font_size=7)
            draw_graph(draw, sensor, normalized, (gx1, gy1, gx2, gy2))

        # Value
        vy = gy2
        unit_w = 25
        if has_data:
            val_str = f"{sensor.buffer[-1]:.1f}"
            val_color = sensor.get_color_gradient(sensor.buffer[-1])
        else:
            val_str = "Err"
            val_color = self.ERR_COLOR

        draw_aligned_text(draw=draw, text=val_str, font_size=24, fill=val_color,
                          box=(px, vy, w - unit_w, value_h),
                          align="right", halign="center",
                          font_path=BOLD_FONT_PATH, autoscale=True, ref_text="000.0")
        if has_data:
            draw_aligned_text(draw=draw, text=sensor.unit_str, font_size=14, fill='white',
                              box=(px + w - unit_w, vy, unit_w, value_h),
                              align="left", halign="center", font_path=FONT_PATH)

        # Footer
        ft_y = py + GRAPH_SIZE - footer_h
        mode = 'left' if panel_idx == 0 else 'right'
        self._draw_footer(draw, disp_manager, px, ft_y, w, h=footer_h, mode=mode)
