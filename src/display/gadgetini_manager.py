#!/usr/bin/env python3
"""Gadgetini TUI Manager — interactive management tool for sensors, viewers, and config."""

import curses
import json
import os
import sys
import types
import configparser
import copy

# ---------------------------------------------------------------------------
# Mock config module so we can import profile_loader without hardware deps
# ---------------------------------------------------------------------------

def _install_mock_config():
    mock = types.ModuleType("config")
    mock.DEBUG = 0
    mock.USE_VIRTUAL_LCD = False
    mock.USE_REAL_DATA = False
    mock.GRAPH_SIZE = 145
    mock.FPS = 10
    mock.FONT_PATH = "fonts/JetBrainsMono-Regular.ttf"
    mock.BOLD_FONT_PATH = "fonts/JetBrainsMono-Bold.ttf"
    mock.EXTRABOLD_FONT_PATH = "fonts/JetBrainsMono-ExtraBold.ttf"
    mock.LIGHT_FONT_PATH = "fonts/JetBrainsMono-Light.ttf"
    mock.THIN_FONT_PATH = "fonts/JetBrainsMono-Thin.ttf"
    mock.ICON_FONT_PATH = "fonts/JetBrainsMonoNerdFont-Bold.ttf"
    sys.modules["config"] = mock

_install_mock_config()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

CONFIG_INI = os.path.join(BASE_DIR, "config.ini")
CONFIG_PY = os.path.join(BASE_DIR, "config.py")

VIEWER_TYPES = [
    "SensorViewer",
    "MultiSensorViewer",
    "DailyViewer",
    "DualSensorViewer",
    "CoolantDetailViewer",
    "TempUtilViewer",
]

VIEWER_PARAMS = {
    "SensorViewer": [
        ("title", "str", True),
        ("sensor_key", "str", True),
        ("sub1_key", "str", False),
        ("sub2_key", "str", False),
        ("fixed_min", "num", False),
        ("fixed_max", "num", False),
        ("sub1_autoscale", "bool", False),
        ("sub2_autoscale", "bool", False),
    ],
    "MultiSensorViewer": [
        ("title", "str", True),
        ("sensor_keys", "list", True),
        ("colors", "colors", True),
        ("labels", "list", True),
    ],
    "DailyViewer": [
        ("title", "str", True),
        ("sensor_keys", "list", True),
        ("colors", "colors", True),
        ("labels", "list", True),
    ],
    "DualSensorViewer": [
        ("panels", "panels", True),
    ],
    "CoolantDetailViewer": [
        ("loops", "loops", True),
    ],
    "TempUtilViewer": [
        ("temp_title", "str", True),
        ("util_title", "str", True),
        ("sensor_keys", "list", True),
        ("colors", "colors", True),
        ("labels", "list", True),
        ("util_keys", "list", True),
    ],
}


# ===========================================================================
# ConfigManager — read/write config.ini preserving key=value format
# ===========================================================================

class ConfigManager:
    def __init__(self, path=CONFIG_INI):
        self.path = path
        self.config = configparser.ConfigParser()
        self.reload()

    def reload(self):
        self.config.read(self.path)

    def get(self, section, key, fallback=None):
        return self.config.get(section, key, fallback=fallback)

    def getint(self, section, key, fallback=0):
        return self.config.getint(section, key, fallback=fallback)

    def getboolean(self, section, key, fallback=False):
        return self.config.getboolean(section, key, fallback=fallback)

    def set(self, section, key, value):
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))

    def remove_option(self, section, key):
        if self.config.has_section(section):
            self.config.remove_option(section, key)

    def sections(self):
        return self.config.sections()

    def items(self, section):
        if self.config.has_section(section):
            return list(self.config.items(section))
        return []

    def save(self):
        """Save config.ini preserving key=value (no spaces around =)."""
        lines = []
        for section in self.config.sections():
            lines.append(f"[{section}]")
            for key, val in self.config.items(section):
                lines.append(f"{key}={val}")
            lines.append("")
        with open(self.path, 'w') as f:
            f.write('\n'.join(lines))


# ===========================================================================
# ProfileData — read/write dg5r.json
# ===========================================================================

class ProfileData:
    def __init__(self, json_path):
        self.path = json_path
        self.data = {}
        self.reload()

    def reload(self):
        with open(self.path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

    def save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
            f.write('\n')

    @property
    def sensors(self):
        return self.data.get('sensors', [])

    @property
    def sensor_templates(self):
        return self.data.get('sensor_templates', [])

    @property
    def viewers(self):
        return self.data.get('viewers', [])

    @property
    def palettes(self):
        return self.data.get('color_palettes', {})

    def all_sensor_keys(self, config):
        """Return all sensor keys including expanded templates."""
        keys = [s['key'] for s in self.sensors]
        for tmpl in self.sensor_templates:
            count = config.getint('PRODUCT', tmpl['count'], fallback=0)
            for i in range(count):
                keys.append(tmpl['key'].replace('{i}', str(i)))
        return keys

    def add_sensor(self, entry):
        self.data.setdefault('sensors', []).append(entry)

    def remove_sensor(self, key):
        self.data['sensors'] = [s for s in self.sensors if s['key'] != key]
        self.data['sensor_templates'] = [
            t for t in self.sensor_templates if t['key'] != key]

    def update_sensor(self, key, entry):
        for i, s in enumerate(self.sensors):
            if s['key'] == key:
                self.data['sensors'][i] = entry
                return
        for i, t in enumerate(self.sensor_templates):
            if t['key'] == key:
                self.data['sensor_templates'][i] = entry
                return

    def add_viewer(self, entry):
        self.data.setdefault('viewers', []).append(entry)

    def remove_viewer(self, key):
        self.data['viewers'] = [v for v in self.viewers if v['key'] != key]

    def update_viewer(self, key, entry):
        for i, v in enumerate(self.viewers):
            if v['key'] == key:
                self.data['viewers'][i] = entry
                return

    def get_viewer(self, key):
        for v in self.viewers:
            if v['key'] == key:
                return v
        return None

    def get_sensor(self, key):
        for s in self.sensors:
            if s['key'] == key:
                return s
        for t in self.sensor_templates:
            if t['key'] == key:
                return t
        return None

    def viewers_using_sensor(self, sensor_key):
        """Return list of viewer keys that reference this sensor key."""
        result = []
        for v in self.viewers:
            params_str = json.dumps(v.get('params', {}))
            if sensor_key in params_str:
                result.append(v['key'])
        return result


# ===========================================================================
# InlineEditor — text field editor with cursor
# ===========================================================================

class InlineEditor:
    def __init__(self, initial="", max_len=60):
        self.text = list(initial)
        self.cursor = len(self.text)
        self.max_len = max_len

    def handle_key(self, ch):
        """Process a key. Returns True if editing continues, False if Enter/Esc."""
        if ch == 10 or ch == curses.KEY_ENTER:
            return False
        elif ch == 27:  # Esc
            self.text = None
            return False
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            if self.cursor > 0:
                self.text.pop(self.cursor - 1)
                self.cursor -= 1
        elif ch == curses.KEY_DC:
            if self.cursor < len(self.text):
                self.text.pop(self.cursor)
        elif ch == curses.KEY_LEFT:
            self.cursor = max(0, self.cursor - 1)
        elif ch == curses.KEY_RIGHT:
            self.cursor = min(len(self.text), self.cursor + 1)
        elif ch == curses.KEY_HOME:
            self.cursor = 0
        elif ch == curses.KEY_END:
            self.cursor = len(self.text)
        elif 32 <= ch <= 126:
            if len(self.text) < self.max_len:
                self.text.insert(self.cursor, chr(ch))
                self.cursor += 1
        return True

    def get_value(self):
        if self.text is None:
            return None
        return ''.join(self.text)

    def render(self, win, y, x, width, attr=0):
        text = ''.join(self.text) if self.text is not None else ""
        display = text[:width]
        win.addnstr(y, x, display + " " * (width - len(display)), width, attr)
        # Draw cursor
        cx = x + min(self.cursor, width - 1)
        if self.cursor < len(text):
            win.addch(y, cx, ord(text[self.cursor]), attr | curses.A_REVERSE)
        else:
            win.addch(y, cx, ord(' '), attr | curses.A_REVERSE)


# ===========================================================================
# Screen classes
# ===========================================================================

class BaseScreen:
    def __init__(self, manager):
        self.manager = manager

    def draw(self, win):
        pass

    def handle_key(self, win, ch):
        """Return next screen or None to pop."""
        return self

    def _draw_header(self, win, title):
        h, w = win.getmaxyx()
        header = f" {title} "
        pad = max(0, w - len(header))
        left = pad // 2
        win.addnstr(0, 0, "=" * left + header + "=" * (pad - left), w - 1,
                     curses.color_pair(1) | curses.A_BOLD)

    def _draw_footer(self, win, text):
        h, w = win.getmaxyx()
        win.addnstr(h - 1, 0, text[:w - 1], w - 1, curses.color_pair(2))

    def _confirm(self, win, msg):
        """Show confirmation dialog. Returns True/False."""
        h, w = win.getmaxyx()
        y = h // 2
        win.addnstr(y, 2, msg + " [y/N] ", w - 4, curses.A_BOLD)
        win.clrtoeol()
        win.refresh()
        ch = win.getch()
        return ch in (ord('y'), ord('Y'))

    def _input_field(self, win, y, x, width, initial="", label=""):
        """Inline text input. Returns string or None on Esc."""
        if label:
            win.addstr(y, x, label)
            x += len(label)
            width -= len(label)
        editor = InlineEditor(initial, max_len=width)
        curses.curs_set(1)
        while True:
            editor.render(win, y, x, width)
            win.refresh()
            ch = win.getch()
            if not editor.handle_key(ch):
                break
        curses.curs_set(0)
        return editor.get_value()

    def _select_list(self, win, title, items, start_y=3):
        """Simple list selection. Returns index or -1 on q/Esc."""
        sel = 0
        while True:
            h, w = win.getmaxyx()
            win.clear()
            self._draw_header(win, title)

            max_visible = h - start_y - 2
            offset = max(0, sel - max_visible + 1)

            for i, item in enumerate(items[offset:offset + max_visible]):
                idx = offset + i
                y = start_y + i
                if y >= h - 1:
                    break
                attr = curses.A_REVERSE if idx == sel else 0
                display = item if isinstance(item, str) else str(item)
                win.addnstr(y, 2, display, w - 4, attr)

            self._draw_footer(win, " Enter:Select  q:Cancel")
            win.refresh()
            ch = win.getch()
            if ch == curses.KEY_UP:
                sel = max(0, sel - 1)
            elif ch == curses.KEY_DOWN:
                sel = min(len(items) - 1, sel + 1)
            elif ch in (10, curses.KEY_ENTER):
                return sel
            elif ch in (ord('q'), 27):
                return -1


# ---------------------------------------------------------------------------
# MainMenuScreen
# ---------------------------------------------------------------------------

class MainMenuScreen(BaseScreen):
    ITEMS = [
        "Viewers",
        "Sensors",
        "Product Config",
        "Display Config",
        "Config Flags",
    ]

    def __init__(self, manager):
        super().__init__(manager)
        self.sel = 0

    def draw(self, win):
        h, w = win.getmaxyx()
        win.clear()
        self._draw_header(win, "Gadgetini Manager")

        for i, item in enumerate(self.ITEMS):
            y = 3 + i * 2
            if y >= h - 1:
                break
            attr = curses.A_REVERSE | curses.A_BOLD if i == self.sel else 0
            marker = ">" if i == self.sel else " "
            win.addnstr(y, 4, f"{marker} {item}", w - 6, attr)

        self._draw_footer(win, " Enter:Select  q:Quit")
        win.refresh()

    def handle_key(self, win, ch):
        if ch == curses.KEY_UP:
            self.sel = max(0, self.sel - 1)
        elif ch == curses.KEY_DOWN:
            self.sel = min(len(self.ITEMS) - 1, self.sel + 1)
        elif ch in (10, curses.KEY_ENTER):
            return self._open_screen()
        elif ch in (ord('q'), 27):
            return None
        return self

    def _open_screen(self):
        screens = [
            ViewersScreen,
            SensorsScreen,
            ProductConfigScreen,
            DisplayConfigScreen,
            ConfigPyScreen,
        ]
        return screens[self.sel](self.manager)


# ---------------------------------------------------------------------------
# ViewersScreen
# ---------------------------------------------------------------------------

class ViewersScreen(BaseScreen):
    def __init__(self, manager):
        super().__init__(manager)
        self.sel = 0

    def _build_items(self):
        """Build display list of viewers with their on/off state."""
        items = []
        for v in self.manager.profile.viewers:
            key = v['key']
            vtype = v['type']
            on = self.manager.cfg.getboolean('DISPLAY', key, fallback=False)
            title = v.get('params', {}).get('title', v.get('params', {}).get('temp_title', ''))
            sensor_count = self._count_sensors(v)
            items.append({
                'key': key, 'type': vtype, 'on': on,
                'title': title, 'sensor_count': sensor_count,
                'entry': v,
            })
        return items

    def _count_sensors(self, viewer):
        params = viewer.get('params', {})
        count = 0
        for k, v in params.items():
            if 'sensor_key' in k:
                if isinstance(v, list):
                    count += len(v)
                elif isinstance(v, str):
                    count += 1
        if 'loops' in params:
            for loop in params['loops']:
                count += len(loop.get('sensor_keys', []))
        if 'panels' in params:
            count += len(params['panels'])
        return count

    def draw(self, win):
        h, w = win.getmaxyx()
        win.clear()
        self._draw_header(win, "Viewers")

        items = self._build_items()
        max_visible = (h - 5) // 3
        offset = max(0, self.sel - max_visible + 1)

        for i, item in enumerate(items[offset:offset + max_visible]):
            idx = offset + i
            y = 2 + i * 3
            if y + 1 >= h - 1:
                break
            attr = curses.A_BOLD if idx == self.sel else 0
            marker = ">" if idx == self.sel else " "
            toggle = "X" if item['on'] else " "
            line1 = f"{marker} [{toggle}] {item['key']:<20s} {item['title']}"
            win.addnstr(y, 1, line1[:w - 2], w - 2, attr)
            line2 = f"      {item['type']}  [{item['sensor_count']} sensors]"
            win.addnstr(y + 1, 1, line2[:w - 2], w - 2,
                        curses.color_pair(3))

        self._draw_footer(win, " Space:Toggle  a:Add  e:Edit  d:Delete  q:Back")
        win.refresh()

    def handle_key(self, win, ch):
        items = self._build_items()
        n = len(items)

        if ch == curses.KEY_UP:
            self.sel = max(0, self.sel - 1)
        elif ch == curses.KEY_DOWN:
            self.sel = min(n - 1, self.sel + 1)
        elif ch == ord(' ') and n > 0:
            item = items[self.sel]
            current = self.manager.cfg.getboolean('DISPLAY', item['key'], fallback=False)
            self.manager.cfg.set('DISPLAY', item['key'], 'off' if current else 'on')
            self.manager.cfg.save()
        elif ch == ord('a'):
            return ViewerAddScreen(self.manager)
        elif ch == ord('e') and n > 0:
            item = items[self.sel]
            return ViewerEditScreen(self.manager, item['key'])
        elif ch == ord('d') and n > 0:
            item = items[self.sel]
            if self._confirm(win, f"Delete viewer '{item['key']}'?"):
                self.manager.profile.remove_viewer(item['key'])
                self.manager.profile.save()
                self.manager.cfg.remove_option('DISPLAY', item['key'])
                self.manager.cfg.save()
                if self.sel >= len(self.manager.profile.viewers):
                    self.sel = max(0, len(self.manager.profile.viewers) - 1)
        elif ch in (ord('q'), 27):
            return None
        return self


# ---------------------------------------------------------------------------
# ViewerEditScreen
# ---------------------------------------------------------------------------

class ViewerEditScreen(BaseScreen):
    def __init__(self, manager, viewer_key):
        super().__init__(manager)
        self.viewer_key = viewer_key
        self.entry = copy.deepcopy(manager.profile.get_viewer(viewer_key))
        self.sel = 0
        self.fields = self._build_fields()

    def _build_fields(self):
        fields = [("key", self.entry['key'])]
        fields.append(("type", self.entry['type']))
        if 'expand' in self.entry:
            fields.append(("expand", self.entry['expand']))
        for k, v in self.entry.get('params', {}).items():
            fields.append((f"params.{k}", v))
        return fields

    def draw(self, win):
        h, w = win.getmaxyx()
        win.clear()
        self._draw_header(win, f"Edit Viewer: {self.viewer_key}")

        max_visible = h - 4
        offset = max(0, self.sel - max_visible + 1)

        for i, (key, val) in enumerate(self.fields[offset:offset + max_visible]):
            idx = offset + i
            y = 2 + i
            if y >= h - 1:
                break
            attr = curses.A_REVERSE if idx == self.sel else 0
            val_str = json.dumps(val, ensure_ascii=False) if not isinstance(val, str) else val
            line = f"  {key}: {val_str}"
            win.addnstr(y, 0, line[:w - 1], w - 1, attr)

        self._draw_footer(win, " Enter:Edit  s:Save  q:Cancel")
        win.refresh()

    def handle_key(self, win, ch):
        if ch == curses.KEY_UP:
            self.sel = max(0, self.sel - 1)
        elif ch == curses.KEY_DOWN:
            self.sel = min(len(self.fields) - 1, self.sel + 1)
        elif ch in (10, curses.KEY_ENTER):
            self._edit_field(win)
        elif ch == ord('s'):
            self._save()
            return None
        elif ch in (ord('q'), 27):
            return None
        return self

    def _edit_field(self, win):
        key, val = self.fields[self.sel]
        if key in ('type',):
            return  # not editable directly
        h, w = win.getmaxyx()
        y = 2 + self.sel
        val_str = json.dumps(val, ensure_ascii=False) if not isinstance(val, str) else val
        new_val = self._input_field(win, min(y, h - 2), 2, w - 4,
                                     initial=val_str, label=f"{key}: ")
        if new_val is None:
            return
        # Try to parse as JSON, fall back to string
        try:
            parsed = json.loads(new_val)
        except (json.JSONDecodeError, ValueError):
            parsed = new_val

        if key == 'key':
            self.entry['key'] = parsed
        elif key == 'expand':
            self.entry['expand'] = parsed
        elif key.startswith('params.'):
            param_key = key[7:]
            self.entry['params'][param_key] = parsed

        self.fields = self._build_fields()

    def _save(self):
        old_key = self.viewer_key
        new_key = self.entry['key']
        self.manager.profile.update_viewer(old_key, self.entry)
        self.manager.profile.save()
        if old_key != new_key:
            on = self.manager.cfg.getboolean('DISPLAY', old_key, fallback=True)
            self.manager.cfg.remove_option('DISPLAY', old_key)
            self.manager.cfg.set('DISPLAY', new_key, 'on' if on else 'off')
            self.manager.cfg.save()


# ---------------------------------------------------------------------------
# ViewerAddScreen
# ---------------------------------------------------------------------------

class ViewerAddScreen(BaseScreen):
    def __init__(self, manager):
        super().__init__(manager)
        self.step = 0  # 0=type, 1=key, 2=params, 3=done
        self.vtype = None
        self.vkey = ""
        self.params = {}
        self.param_fields = []
        self.param_idx = 0

    def draw(self, win):
        h, w = win.getmaxyx()
        win.clear()
        self._draw_header(win, "Add Viewer")

        if self.step == 0:
            win.addnstr(2, 2, "Select viewer type:", w - 4, curses.A_BOLD)
        elif self.step == 1:
            win.addnstr(2, 2, f"Type: {self.vtype}", w - 4)
            win.addnstr(3, 2, "Enter config key:", w - 4, curses.A_BOLD)
        elif self.step == 2:
            win.addnstr(2, 2, f"Type: {self.vtype}  Key: {self.vkey}", w - 4)
            win.addnstr(3, 2, "Fill parameters:", w - 4, curses.A_BOLD)
            for i, (name, ptype, req) in enumerate(self.param_fields):
                y = 5 + i
                if y >= h - 1:
                    break
                marker = "*" if req else " "
                val = self.params.get(name, "")
                val_str = json.dumps(val, ensure_ascii=False) if not isinstance(val, str) else val
                attr = curses.A_REVERSE if i == self.param_idx else 0
                win.addnstr(y, 2, f"{marker}{name}: {val_str}", w - 4, attr)

        self._draw_footer(win, " Enter:Next  q:Cancel")
        win.refresh()

    def handle_key(self, win, ch):
        if ch in (ord('q'), 27):
            return None

        if self.step == 0:
            idx = self._select_list(win, "Select Viewer Type", VIEWER_TYPES)
            if idx < 0:
                return None
            self.vtype = VIEWER_TYPES[idx]
            self.param_fields = VIEWER_PARAMS.get(self.vtype, [])
            self.step = 1
            return self

        elif self.step == 1:
            h, w = win.getmaxyx()
            key = self._input_field(win, 4, 2, w - 4, label="Key: ")
            if key is None or key.strip() == "":
                return None
            self.vkey = key.strip()
            self.step = 2
            return self

        elif self.step == 2:
            if ch == curses.KEY_UP:
                self.param_idx = max(0, self.param_idx - 1)
            elif ch == curses.KEY_DOWN:
                self.param_idx = min(len(self.param_fields) - 1, self.param_idx + 1)
            elif ch in (10, curses.KEY_ENTER):
                self._edit_param(win)
            elif ch == ord('s'):
                return self._finish_add()
            return self

        return self

    def _edit_param(self, win):
        if not self.param_fields:
            return
        name, ptype, req = self.param_fields[self.param_idx]
        h, w = win.getmaxyx()
        current = self.params.get(name, "")
        if not isinstance(current, str):
            current = json.dumps(current, ensure_ascii=False)
        val = self._input_field(win, h - 3, 2, w - 4,
                                 initial=current, label=f"{name}: ")
        if val is None:
            return
        try:
            parsed = json.loads(val)
        except (json.JSONDecodeError, ValueError):
            parsed = val
        self.params[name] = parsed

    def _finish_add(self):
        entry = {
            "key": self.vkey,
            "type": self.vtype,
            "params": self.params,
        }
        self.manager.profile.add_viewer(entry)
        self.manager.profile.save()
        self.manager.cfg.set('DISPLAY', self.vkey, 'on')
        self.manager.cfg.save()
        return None  # back to viewers


# ---------------------------------------------------------------------------
# SensorsScreen
# ---------------------------------------------------------------------------

class SensorsScreen(BaseScreen):
    def __init__(self, manager):
        super().__init__(manager)
        self.sel = 0

    def _build_items(self):
        items = []
        for s in self.manager.profile.sensors:
            items.append(('sensor', s))
        for t in self.manager.profile.sensor_templates:
            items.append(('template', t))
        return items

    def draw(self, win):
        h, w = win.getmaxyx()
        win.clear()
        self._draw_header(win, "Sensors")

        items = self._build_items()
        col_w = max(18, w // 4)

        # Header row
        win.addnstr(2, 2, f"{'Key':<{col_w}} {'Title':<{col_w}} {'Unit':<6}",
                     w - 4, curses.A_BOLD | curses.color_pair(1))
        win.addnstr(3, 2, "-" * (w - 4), w - 4, curses.color_pair(3))

        max_visible = h - 6
        offset = max(0, self.sel - max_visible + 1)
        y = 4
        prev_type = None

        for i, (stype, entry) in enumerate(items[offset:offset + max_visible]):
            idx = offset + i
            if y >= h - 1:
                break

            # Separator between sensors and templates
            if stype == 'template' and prev_type == 'sensor':
                win.addnstr(y, 2, "--- Templates " + "-" * (w - 18), w - 4,
                            curses.color_pair(3))
                y += 1
                if y >= h - 1:
                    break

            attr = curses.A_REVERSE if idx == self.sel else 0
            key = entry['key']
            title = entry.get('title', '')
            unit = entry.get('unit', '')
            line = f" {key:<{col_w}} {title:<{col_w}} {unit:<6}"

            win.addnstr(y, 1, line[:w - 2], w - 2, attr)

            if stype == 'template':
                count_key = entry.get('count', '')
                count_val = self.manager.cfg.getint('PRODUCT', count_key, fallback=0)
                info = f"   (x{count_val}, from {count_key})"
                y += 1
                if y < h - 1:
                    win.addnstr(y, 1, info[:w - 2], w - 2, curses.color_pair(3))

            y += 1
            prev_type = stype

        self._draw_footer(win, " Enter:Detail  a:Add  e:Edit  d:Delete  q:Back")
        win.refresh()

    def handle_key(self, win, ch):
        items = self._build_items()
        n = len(items)

        if ch == curses.KEY_UP:
            self.sel = max(0, self.sel - 1)
        elif ch == curses.KEY_DOWN:
            self.sel = min(n - 1, self.sel + 1)
        elif ch in (10, curses.KEY_ENTER) and n > 0:
            stype, entry = items[self.sel]
            return SensorDetailScreen(self.manager, entry, stype == 'template')
        elif ch == ord('a'):
            return SensorAddScreen(self.manager)
        elif ch == ord('e') and n > 0:
            stype, entry = items[self.sel]
            return SensorEditScreen(self.manager, entry['key'], stype == 'template')
        elif ch == ord('d') and n > 0:
            stype, entry = items[self.sel]
            key = entry['key']
            refs = self.manager.profile.viewers_using_sensor(key)
            msg = f"Delete sensor '{key}'?"
            if refs:
                msg += f" (used by: {', '.join(refs)})"
            if self._confirm(win, msg):
                self.manager.profile.remove_sensor(key)
                self.manager.profile.save()
                if self.sel >= len(self._build_items()):
                    self.sel = max(0, len(self._build_items()) - 1)
        elif ch in (ord('q'), 27):
            return None
        return self


# ---------------------------------------------------------------------------
# SensorDetailScreen
# ---------------------------------------------------------------------------

class SensorDetailScreen(BaseScreen):
    def __init__(self, manager, entry, is_template=False):
        super().__init__(manager)
        self.entry = entry
        self.is_template = is_template

    def draw(self, win):
        h, w = win.getmaxyx()
        win.clear()
        kind = "Template" if self.is_template else "Sensor"
        self._draw_header(win, f"{kind}: {self.entry['key']}")

        y = 3
        for k, v in self.entry.items():
            if y >= h - 1:
                break
            val_str = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
            win.addnstr(y, 2, f"{k}: ", w - 4, curses.A_BOLD)
            win.addnstr(y, 2 + len(k) + 2, val_str[:w - len(k) - 6], w - len(k) - 6)
            y += 1

        if self.is_template:
            y += 1
            count_key = self.entry.get('count', '')
            count_val = self.manager.cfg.getint('PRODUCT', count_key, fallback=0)
            if y < h - 1:
                win.addnstr(y, 2, f"Expands to {count_val} sensors ({count_key})",
                            w - 4, curses.color_pair(2))

        refs = self.manager.profile.viewers_using_sensor(self.entry['key'])
        if refs:
            y += 2
            if y < h - 1:
                win.addnstr(y, 2, f"Used by viewers: {', '.join(refs)}",
                            w - 4, curses.color_pair(3))

        self._draw_footer(win, " q:Back")
        win.refresh()

    def handle_key(self, win, ch):
        if ch in (ord('q'), 27):
            return None
        return self


# ---------------------------------------------------------------------------
# SensorEditScreen
# ---------------------------------------------------------------------------

class SensorEditScreen(BaseScreen):
    def __init__(self, manager, sensor_key, is_template=False):
        super().__init__(manager)
        self.sensor_key = sensor_key
        self.is_template = is_template
        self.entry = copy.deepcopy(manager.profile.get_sensor(sensor_key))
        self.fields = list(self.entry.items())
        self.sel = 0

    def draw(self, win):
        h, w = win.getmaxyx()
        win.clear()
        kind = "Template" if self.is_template else "Sensor"
        self._draw_header(win, f"Edit {kind}: {self.sensor_key}")

        max_visible = h - 4
        offset = max(0, self.sel - max_visible + 1)

        for i, (key, val) in enumerate(self.fields[offset:offset + max_visible]):
            idx = offset + i
            y = 2 + i
            if y >= h - 1:
                break
            attr = curses.A_REVERSE if idx == self.sel else 0
            val_str = json.dumps(val, ensure_ascii=False) if not isinstance(val, str) else val
            line = f"  {key}: {val_str}"
            win.addnstr(y, 0, line[:w - 1], w - 1, attr)

        self._draw_footer(win, " Enter:Edit  s:Save  q:Cancel")
        win.refresh()

    def handle_key(self, win, ch):
        if ch == curses.KEY_UP:
            self.sel = max(0, self.sel - 1)
        elif ch == curses.KEY_DOWN:
            self.sel = min(len(self.fields) - 1, self.sel + 1)
        elif ch in (10, curses.KEY_ENTER):
            self._edit_field(win)
        elif ch == ord('s'):
            self._save()
            return None
        elif ch in (ord('q'), 27):
            return None
        return self

    def _edit_field(self, win):
        key, val = self.fields[self.sel]
        h, w = win.getmaxyx()
        val_str = json.dumps(val, ensure_ascii=False) if not isinstance(val, str) else val
        y = min(2 + self.sel, h - 2)
        new_val = self._input_field(win, y, 2, w - 4,
                                     initial=val_str, label=f"{key}: ")
        if new_val is None:
            return
        try:
            parsed = json.loads(new_val)
        except (json.JSONDecodeError, ValueError):
            parsed = new_val
        self.entry[key] = parsed
        self.fields = list(self.entry.items())

    def _save(self):
        self.manager.profile.update_sensor(self.sensor_key, self.entry)
        self.manager.profile.save()


# ---------------------------------------------------------------------------
# SensorAddScreen
# ---------------------------------------------------------------------------

class SensorAddScreen(BaseScreen):
    FIELDS = [
        ("key", "str", True),
        ("title", "str", True),
        ("unit", "str", True),
        ("min", "num", True),
        ("max", "num", True),
        ("read_rate", "num", False),
    ]
    SOURCE_OPTIONS = ["redis_key", "redis_keys", "formula"]

    def __init__(self, manager):
        super().__init__(manager)
        self.step = 0  # 0=type_choice, 1=fields, 2=source, 3=source_detail, 4=extras
        self.is_template = False
        self.data = {}
        self.sel = 0

    def draw(self, win):
        h, w = win.getmaxyx()
        win.clear()
        self._draw_header(win, "Add Sensor")

        if self.step == 0:
            win.addnstr(2, 2, "Sensor type:", w - 4, curses.A_BOLD)
        else:
            y = 2
            for k, v in self.data.items():
                if y >= h - 2:
                    break
                val_s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
                win.addnstr(y, 2, f"{k}: {val_s}", w - 4)
                y += 1

            if self.step == 1:
                win.addnstr(y + 1, 2, "Fill basic fields (Enter to edit, s to continue):",
                            w - 4, curses.A_BOLD)
            elif self.step == 2:
                win.addnstr(y + 1, 2, "Select data source:", w - 4, curses.A_BOLD)
            elif self.step == 3:
                win.addnstr(y + 1, 2, "Enter source detail:", w - 4, curses.A_BOLD)

        self._draw_footer(win, " Enter:Next  s:Save  q:Cancel")
        win.refresh()

    def handle_key(self, win, ch):
        if ch in (ord('q'), 27) and self.step != 0:
            return None

        if self.step == 0:
            choices = ["Static sensor", "Template"]
            idx = self._select_list(win, "Sensor Type", choices)
            if idx < 0:
                return None
            self.is_template = (idx == 1)
            if self.is_template:
                self.data['count'] = ''
            self.step = 1
            return self

        elif self.step == 1:
            return self._handle_fields(win, ch)

        elif self.step == 2:
            idx = self._select_list(win, "Data Source", self.SOURCE_OPTIONS)
            if idx < 0:
                return self
            src = self.SOURCE_OPTIONS[idx]
            self.step = 3
            self._current_source = src
            return self

        elif self.step == 3:
            return self._handle_source_detail(win, ch)

        return self

    def _handle_fields(self, win, ch):
        h, w = win.getmaxyx()
        fields = list(self.FIELDS)
        if self.is_template:
            fields.insert(0, ("count", "str", True))

        if ch in (10, curses.KEY_ENTER):
            if self.sel < len(fields):
                name, ptype, req = fields[self.sel]
                current = self.data.get(name, "")
                if not isinstance(current, str):
                    current = str(current)
                val = self._input_field(win, h - 3, 2, w - 4,
                                         initial=current, label=f"{name}: ")
                if val is not None:
                    try:
                        parsed = json.loads(val)
                    except (json.JSONDecodeError, ValueError):
                        parsed = val
                    self.data[name] = parsed
        elif ch == curses.KEY_UP:
            self.sel = max(0, self.sel - 1)
        elif ch == curses.KEY_DOWN:
            self.sel = min(len(fields) - 1, self.sel + 1)
        elif ch == ord('s'):
            self.step = 2
            self.sel = 0
        return self

    def _handle_source_detail(self, win, ch):
        h, w = win.getmaxyx()
        src = self._current_source
        val = self._input_field(win, h - 3, 2, w - 4, label=f"{src}: ")
        if val is not None:
            try:
                parsed = json.loads(val)
            except (json.JSONDecodeError, ValueError):
                parsed = val
            self.data[src] = parsed
        return self._finish_add(win)

    def _finish_add(self, win):
        h, w = win.getmaxyx()
        # Optional icon and label
        icon = self._input_field(win, h - 3, 2, w - 4, label="icon (hex, optional): ")
        if icon and icon.strip():
            self.data['icon'] = icon.strip()
        label = self._input_field(win, h - 3, 2, w - 4, label="label (optional): ")
        if label and label.strip():
            self.data['label'] = label.strip()

        if self.is_template:
            self.manager.profile.data.setdefault('sensor_templates', []).append(self.data)
        else:
            self.manager.profile.add_sensor(self.data)
        self.manager.profile.save()
        return None


# ---------------------------------------------------------------------------
# ProductConfigScreen
# ---------------------------------------------------------------------------

class ProductConfigScreen(BaseScreen):
    def __init__(self, manager):
        super().__init__(manager)
        self.sel = 0

    def _items(self):
        return self.manager.cfg.items('PRODUCT')

    def draw(self, win):
        h, w = win.getmaxyx()
        win.clear()
        self._draw_header(win, "Product Config")

        items = self._items()
        for i, (key, val) in enumerate(items):
            y = 3 + i
            if y >= h - 1:
                break
            attr = curses.A_REVERSE if i == self.sel else 0
            line = f"  {key:<16s} [{val}]"
            win.addnstr(y, 0, line[:w - 1], w - 1, attr)

        self._draw_footer(win, " Enter:Edit  q:Back")
        win.refresh()

    def handle_key(self, win, ch):
        items = self._items()
        if ch == curses.KEY_UP:
            self.sel = max(0, self.sel - 1)
        elif ch == curses.KEY_DOWN:
            self.sel = min(len(items) - 1, self.sel + 1)
        elif ch in (10, curses.KEY_ENTER) and items:
            key, val = items[self.sel]
            h, w = win.getmaxyx()
            new_val = self._input_field(win, 3 + self.sel, 0, w - 2,
                                         initial=val, label=f"  {key}: ")
            if new_val is not None:
                self.manager.cfg.set('PRODUCT', key, new_val)
                self.manager.cfg.save()
        elif ch in (ord('q'), 27):
            return None
        return self


# ---------------------------------------------------------------------------
# DisplayConfigScreen
# ---------------------------------------------------------------------------

class DisplayConfigScreen(BaseScreen):
    def __init__(self, manager):
        super().__init__(manager)
        self.sel = 0

    def _items(self):
        return self.manager.cfg.items('DISPLAY')

    def draw(self, win):
        h, w = win.getmaxyx()
        win.clear()
        self._draw_header(win, "Display Config")

        items = self._items()
        for i, (key, val) in enumerate(items):
            y = 3 + i
            if y >= h - 1:
                break
            attr = curses.A_REVERSE if i == self.sel else 0
            if val in ('on', 'off'):
                toggle = "[X]" if val == 'on' else "[ ]"
                line = f"  {key:<20s} {toggle}"
            else:
                line = f"  {key:<20s} [{val}]"
            win.addnstr(y, 0, line[:w - 1], w - 1, attr)

        self._draw_footer(win, " Space:Toggle  Enter:Edit  q:Back")
        win.refresh()

    def handle_key(self, win, ch):
        items = self._items()
        if ch == curses.KEY_UP:
            self.sel = max(0, self.sel - 1)
        elif ch == curses.KEY_DOWN:
            self.sel = min(len(items) - 1, self.sel + 1)
        elif ch == ord(' ') and items:
            key, val = items[self.sel]
            if val in ('on', 'off'):
                self.manager.cfg.set('DISPLAY', key, 'off' if val == 'on' else 'on')
                self.manager.cfg.save()
        elif ch in (10, curses.KEY_ENTER) and items:
            key, val = items[self.sel]
            h, w = win.getmaxyx()
            new_val = self._input_field(win, 3 + self.sel, 0, w - 2,
                                         initial=val, label=f"  {key}: ")
            if new_val is not None:
                self.manager.cfg.set('DISPLAY', key, new_val)
                self.manager.cfg.save()
        elif ch in (ord('q'), 27):
            return None
        return self


# ---------------------------------------------------------------------------
# ConfigPyScreen (read-only)
# ---------------------------------------------------------------------------

class ConfigPyScreen(BaseScreen):
    def __init__(self, manager):
        super().__init__(manager)
        self.lines = self._parse_config_py()
        self.scroll = 0

    def _parse_config_py(self):
        lines = []
        try:
            with open(CONFIG_PY, 'r') as f:
                for line in f:
                    line = line.rstrip('\n')
                    # Show assignments and comments, skip hardware blocks
                    if line.startswith('if ') or line.startswith('else'):
                        break
                    lines.append(line)
        except FileNotFoundError:
            lines.append("config.py not found")
        return lines

    def draw(self, win):
        h, w = win.getmaxyx()
        win.clear()
        self._draw_header(win, "Config Flags (read-only)")

        max_visible = h - 3
        for i, line in enumerate(self.lines[self.scroll:self.scroll + max_visible]):
            y = 2 + i
            if y >= h - 1:
                break
            if '=' in line and not line.strip().startswith('#'):
                win.addnstr(y, 2, line[:w - 4], w - 4, curses.A_BOLD)
            else:
                win.addnstr(y, 2, line[:w - 4], w - 4, curses.color_pair(3))

        self._draw_footer(win, " q:Back")
        win.refresh()

    def handle_key(self, win, ch):
        h, _ = win.getmaxyx()
        max_visible = h - 3
        if ch == curses.KEY_UP:
            self.scroll = max(0, self.scroll - 1)
        elif ch == curses.KEY_DOWN:
            self.scroll = min(max(0, len(self.lines) - max_visible), self.scroll + 1)
        elif ch in (ord('q'), 27):
            return None
        return self


# ===========================================================================
# GadgetiniManager — app loop
# ===========================================================================

class GadgetiniManager:
    def __init__(self):
        self.cfg = ConfigManager()
        profile_name = self.cfg.get('PRODUCT', 'name', fallback='dg5r')
        json_path = os.path.join(BASE_DIR, 'profiles', f'{profile_name}.json')
        self.profile = ProfileData(json_path)

    def run(self, stdscr):
        curses.curs_set(0)
        curses.use_default_colors()

        # Color pairs
        curses.init_pair(1, curses.COLOR_CYAN, -1)     # header
        curses.init_pair(2, curses.COLOR_YELLOW, -1)    # footer
        curses.init_pair(3, curses.COLOR_WHITE, -1)     # dim
        curses.init_pair(4, curses.COLOR_GREEN, -1)     # success
        curses.init_pair(5, curses.COLOR_RED, -1)       # error

        screen_stack = [MainMenuScreen(self)]

        while screen_stack:
            current = screen_stack[-1]
            current.draw(stdscr)
            ch = stdscr.getch()

            result = current.handle_key(stdscr, ch)
            if result is None:
                screen_stack.pop()
            elif result is not current:
                screen_stack.append(result)


def main():
    manager = GadgetiniManager()
    curses.wrapper(manager.run)


if __name__ == "__main__":
    main()
