import numpy as np

from config import (DEBUG, GRAPH_SIZE,
                    FONT_PATH, BOLD_FONT_PATH, LIGHT_FONT_PATH)
from draw_utils import draw_aligned_text


class BaseViewer:
    """Common base for all display viewers."""

    ERR_COLOR = (128, 128, 128)

    def __init__(self, host_data=0):
        self.active = 1
        self.host_data = host_data
        #print(f"host_data = {self.host_data}")

    def _setup(self, draw, disp_manager):
        """Clear screen, draw debug border, return offset tuple."""
        if disp_manager.horizontal == 1:
            offset = (disp_manager.x_offset, disp_manager.y_offset)
        else:
            offset = (disp_manager.y_offset, disp_manager.x_offset)
        draw.rectangle((0, 0, disp_manager.width, disp_manager.height), fill='black')
        if DEBUG != 0:
            draw.rectangle((offset[0], offset[1],
                            disp_manager.width, disp_manager.height),
                           outline=(0, 0, 255), width=3)
        return offset

    def _boxes(self, offset, horizontal):
        """Standard two-box layout: graph box (left/top) + data box (right/bottom)."""
        gx1, gy1 = offset
        gx2, gy2 = gx1 + GRAPH_SIZE, gy1 + GRAPH_SIZE
        if horizontal == 1:
            dx1, dy1 = gx2 + 5, gy1
        else:
            dx1, dy1 = gx1, gy2 + 5
        dx2, dy2 = dx1 + GRAPH_SIZE, dy1 + GRAPH_SIZE
        return (gx1, gy1, gx2, gy2), (dx1, dy1, dx2, dy2)

    def _draw_title(self, draw, text, x, y, w, h=15):
        """Unified title: bold, white, centered, autoscale."""
        draw_aligned_text(draw=draw, text=text, font_size=15, fill='white',
                          box=(x, y, w, h), align="center", halign="center",
                          font_path=BOLD_FONT_PATH, autoscale=True)

    def _draw_footer(self, draw, disp_manager, x, y, w, h=10, mode='both'):
        """Footer: left=leak+level status dots, right=IP+version.
        mode: 'both'|'left'|'right'
          'left'  → leak/level indicators only (used by left panel in dual-panel layouts)
          'right' → IP + version only         (used by right panel in dual-panel layouts)
          'both'  → left 45% status, right 55% IP+version
        """
        dot_r = 3
        dot_cy = y + h // 2

        # --- Status indicators (LEAK + LEVEL) ---
        if mode in ('both', 'left'):
            status_w = int(w * 0.45) if mode == 'both' else w
            half_status = status_w // 2

            leak_sensor = disp_manager.sensors.get('coolant_leak')
            if leak_sensor and len(leak_sensor.buffer) > 0:
                leak_color = (0, 200, 80) if int(round(leak_sensor.buffer[-1])) == 0 else (255, 60, 60)
            else:
                leak_color = self.ERR_COLOR

            level_sensor = disp_manager.sensors.get('coolant_level')
            if level_sensor and len(level_sensor.buffer) > 0:
                level_color = (0, 200, 80) if int(round(level_sensor.buffer[-1])) == 1 else (255, 60, 60)
            else:
                level_color = self.ERR_COLOR

            # Leak dot + label
            lk_cx = x + dot_r + 2
            draw.ellipse((lk_cx - dot_r, dot_cy - dot_r,
                          lk_cx + dot_r, dot_cy + dot_r), fill=leak_color)
            draw_aligned_text(draw=draw, text="LEAK", font_size=7, fill='white',
                              box=(x + dot_r * 2 + 5, y, half_status - dot_r * 2 - 5, h),
                              align="left", halign="center", font_path=LIGHT_FONT_PATH)

            # Level dot + label
            lv_x = x + half_status
            lv_cx = lv_x + dot_r + 2
            draw.ellipse((lv_cx - dot_r, dot_cy - dot_r,
                          lv_cx + dot_r, dot_cy + dot_r), fill=level_color)
            draw_aligned_text(draw=draw, text="LEVEL", font_size=7, fill='white',
                              box=(lv_x + dot_r * 2 + 5, y, half_status - dot_r * 2 - 5, h),
                              align="left", halign="center", font_path=LIGHT_FONT_PATH)

        # --- IP + version ---
        if mode in ('both', 'right'):
            if mode == 'both':
                info_x = x + int(w * 0.45)
                info_w = w - int(w * 0.45)
            else:
                info_x, info_w = x, w
            draw_aligned_text(draw=draw, text=disp_manager.ip_addr,
                              font_size=7, fill='white',
                              box=(info_x, y, info_w, h), align="left", halign="center",
                              font_path=LIGHT_FONT_PATH)
            draw_aligned_text(draw=draw, text=disp_manager.version,
                              font_size=7, fill='gray',
                              box=(info_x, y, info_w, h), align="right", halign="center",
                              font_path=LIGHT_FONT_PATH)

    def _normalize(self, sensor_list, graph_h):
        """Shared min/max normalization for multiple sensor buffers."""
        all_values = []
        for s in sensor_list:
            if len(s.buffer) > 0:
                all_values.extend(s.buffer)
        if not all_values:
            return None, None, []
        min_val = int(np.min(all_values) * 0.95)
        max_val = int(np.max(all_values) * 1.05)
        if min_val == max_val:
            max_val = min_val + 1
        normalized = []
        for s in sensor_list:
            if len(s.buffer) >= 2:
                norm = np.interp(s.buffer, (min_val, max_val), (8, graph_h - 8))
                normalized.append(norm)
            else:
                normalized.append(np.array([]))
        return min_val, max_val, normalized

    def _normalize_single(self, sensor, graph_h, fixed_min=None, fixed_max=None):
        """Normalize a single sensor buffer."""
        if fixed_min is not None:
            min_val, max_val = fixed_min, fixed_max
        else:
            min_val = int(np.min(sensor.buffer) * 0.95)
            max_val = int(np.max(sensor.buffer) * 1.05)
        if min_val == max_val:
            max_val = min_val + 1
        normalized = np.interp(sensor.buffer, (min_val, max_val), (8, graph_h - 8))
        return min_val, max_val, normalized

    def _draw_graph_labels(self, draw, min_val, max_val, unit_str,
                           gx, gy1, gy2, w, font_size=8,
                           min_fill='white', max_fill='white'):
        """Draw min/max value labels on graph edges."""
        draw_aligned_text(draw=draw, text=f"{round(max_val):.1f}{unit_str}",
                          font_size=font_size, fill=max_fill,
                          box=(gx, gy1, w, font_size),
                          align="center", halign="top", font_path=FONT_PATH)
        draw_aligned_text(draw=draw, text=f"{round(min_val):.1f}{unit_str}",
                          font_size=font_size, fill=min_fill,
                          box=(gx, gy2 - font_size, w, font_size),
                          align="center", halign="bottom", font_path=FONT_PATH)

    def _draw_legend_row(self, draw, sensor, label, color, cx, cy, row_h,
                         col_w, sq=5):
        """Draw one legend entry: color square + label + value + unit."""
        sq_pad = sq + 3
        label_w = 22
        unit_w = 14

        sq_y = cy + (row_h - sq) // 2
        draw.rectangle((cx + 2, sq_y, cx + 2 + sq, sq_y + sq), fill=color)

        draw_aligned_text(draw=draw, text=label, font_size=8, fill='white',
                          box=(cx + sq_pad, cy, label_w, row_h),
                          align="left", halign="center", font_path=FONT_PATH)

        if len(sensor.buffer) > 0:
            val_str = f"{sensor.buffer[-1]:.1f}"
            val_color = color
        elif sensor.error:
            val_str = "Err"
            val_color = self.ERR_COLOR
        else:
            return

        val_w = col_w - sq_pad - label_w - unit_w - 2
        val_x = cx + sq_pad + label_w

        draw_aligned_text(draw=draw, text=val_str, font_size=10, fill=val_color,
                          box=(val_x, cy, val_w, row_h),
                          align="right", halign="center",
                          font_path=BOLD_FONT_PATH,
                          autoscale=True, ref_text="000.0")
        if len(sensor.buffer) > 0:
            draw_aligned_text(draw=draw, text=sensor.unit_str,
                              font_size=7, fill='white',
                              box=(val_x + val_w, cy, unit_w, row_h),
                              align="left", halign="center", font_path=FONT_PATH)
