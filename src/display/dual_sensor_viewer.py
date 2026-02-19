from config import (DEBUG, GRAPH_SIZE, FONT_PATH, BOLD_FONT_PATH)
from base_viewer import BaseViewer
from draw_utils import draw_aligned_text, draw_graph


class DualSensorViewer(BaseViewer):
    """Two independent sensor graphs displayed side by side."""

    def __init__(self, panels, status_badges=None):
        """
        panels: list of 2 dicts, each with:
            'title': str
            'sensor_key': str
        status_badges: optional list of dicts, one per panel, each with:
            'key': sensor key (bool 0/1)
            'label': display label (e.g. 'LEVEL')
            'ok_value': value that means OK (0 or 1)
            'ok_text': text shown when OK
            'alert_text': text shown when not OK
        """
        super().__init__()
        self.panels = panels
        self.status_badges = status_badges or []

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
        badge_h = 18 if self.status_badges else 0
        graph_h = 88 - badge_h
        value_h = 30
        footer_h = 12

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

        # Status badge (below graph, above value)
        if badge_h > 0 and panel_idx < len(self.status_badges):
            self._draw_status_badge(
                draw, disp_manager,
                self.status_badges[panel_idx],
                px, gy2, w, badge_h
            )

        # Value
        vy = gy2 + badge_h
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

    def _draw_status_badge(self, draw, disp_manager, badge, px, by, w, h):
        """Draw a boolean status indicator (OK / ALERT) in the given area."""
        key = badge['key']
        label = badge.get('label', key)
        ok_value = badge.get('ok_value', 1)
        ok_text = badge.get('ok_text', 'OK')
        alert_text = badge.get('alert_text', 'WARN')

        sensor = disp_manager.sensors.get(key)
        if sensor is None:
            return

        if len(sensor.buffer) > 0:
            val = int(round(sensor.buffer[-1]))
            is_ok = (val == ok_value)
        elif sensor.error:
            is_ok = None
        else:
            return

        if is_ok is None:
            status_text = "ERR"
            color = self.ERR_COLOR
        elif is_ok:
            status_text = ok_text
            color = (0, 200, 80)
        else:
            status_text = alert_text
            color = (255, 60, 60)

        # Colored dot indicator
        dot_r = 4
        dot_cx = px + dot_r + 3
        dot_cy = by + h // 2
        draw.ellipse(
            (dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r),
            fill=color
        )

        # Label (left half)
        label_x = px + dot_r * 2 + 8
        label_w = w // 2 - dot_r * 2 - 8
        draw_aligned_text(draw=draw, text=label, font_size=9, fill='white',
                          box=(label_x, by, label_w, h),
                          align="left", halign="center", font_path=FONT_PATH)

        # Status text (right half)
        status_x = px + w // 2
        status_w = w // 2
        draw_aligned_text(draw=draw, text=status_text, font_size=9, fill=color,
                          box=(status_x, by, status_w, h),
                          align="right", halign="center", font_path=BOLD_FONT_PATH)
