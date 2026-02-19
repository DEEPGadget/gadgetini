"""Load sensor/viewer definitions from a JSON profile file."""

import json

from sensor_data import SensorData
from viewer import SensorViewer
from multi_viewer import MultiSensorViewer
from daily_viewer import DailyViewer
from coolant_detail_viewer import CoolantDetailViewer
from dual_sensor_viewer import DualSensorViewer
from temp_util_viewer import TempUtilViewer


VIEWER_CLASSES = {
    "SensorViewer": SensorViewer,
    "MultiSensorViewer": MultiSensorViewer,
    "DailyViewer": DailyViewer,
    "DualSensorViewer": DualSensorViewer,
    "CoolantDetailViewer": CoolantDetailViewer,
    "TempUtilViewer": TempUtilViewer,
}


def _parse_icon(hex_str):
    """'0xf0510' -> chr(0xf0510) unicode character."""
    if not hex_str:
        return None
    return chr(int(hex_str, 16))


def _make_formula(expr_str):
    """Convert expression string to a callable. Only safe builtins allowed."""
    allowed = {"float": float, "int": int, "max": max, "min": min, "abs": abs}
    return lambda r: eval(expr_str, {"__builtins__": {}, "r": r, **allowed})


def _expand_templates(templates, config):
    """Expand sensor_templates using count from config. {i} -> 0,1,...,N-1."""
    result = []
    for tmpl in templates:
        count_key = tmpl['count']
        count = config.getint('PRODUCT', count_key, fallback=0) if config else 0
        for i in range(count):
            sensor = {}
            for k, v in tmpl.items():
                if k == 'count':
                    continue
                sensor[k] = v.replace('{i}', str(i)) if isinstance(v, str) else v
            result.append(sensor)
    return result


def _build_sensor(entry, redis):
    """Convert a single sensor JSON entry to a SensorData instance."""
    kwargs = {
        "title_str": entry['title'],
        "unit_str": entry['unit'],
        "min_val": entry['min'],
        "max_val": entry['max'],
        "read_rate": entry.get('read_rate', 1),
        "redis": redis,
        "host_data": int(entry.get('host_data', 0)),
        "icon": _parse_icon(entry.get('icon')),
        "label": entry.get('label'),
    }
    if 'formula' in entry:
        kwargs['formula'] = _make_formula(entry['formula'])
    elif 'redis_keys' in entry:
        kwargs['redis_keys'] = entry['redis_keys']
    elif 'redis_key' in entry:
        kwargs['redis_key'] = entry['redis_key']
    return SensorData(**kwargs)


def load_sensors(json_path, redis, config=None):
    """Load sensors + sensor_templates from JSON into a SensorData dict."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    sensors = {}
    for entry in data.get('sensors', []):
        sensors[entry['key']] = _build_sensor(entry, redis)

    expanded = _expand_templates(data.get('sensor_templates', []), config)
    for entry in expanded:
        sensors[entry['key']] = _build_sensor(entry, redis)

    return sensors


def _expand_viewer_params(params, count, palettes):
    """Expand {i} patterns and $PALETTE references in viewer params."""
    expanded = {}
    for k, v in params.items():
        if isinstance(v, str) and '{i}' in v:
            expanded[k] = [v.replace('{i}', str(i)) for i in range(count)]
        elif isinstance(v, str) and v.startswith('$'):
            palette_name = v[1:]
            palette = palettes[palette_name]
            expanded[k] = [tuple(c) for c in palette[:count]]
        elif isinstance(v, list):
            # Nested dicts (e.g. loops, panels) — recurse into each element
            if all(isinstance(item, dict) for item in v):
                expanded[k] = [_expand_viewer_params(item, count, palettes) for item in v]
            elif all(isinstance(c, list) for c in v):
                # Color lists: [[r,g,b], ...] -> [(r,g,b), ...]
                expanded[k] = [tuple(c) for c in v]
            else:
                expanded[k] = v
        elif isinstance(v, dict):
            expanded[k] = _expand_viewer_params(v, count, palettes)
        else:
            expanded[k] = v
    return expanded


def _resolve_colors(params, palettes):
    """Resolve $PALETTE references and convert color lists to tuples (no expand)."""
    resolved = {}
    for k, v in params.items():
        if isinstance(v, str) and v.startswith('$'):
            palette_name = v[1:]
            resolved[k] = [tuple(c) for c in palettes[palette_name]]
        elif isinstance(v, list):
            if all(isinstance(item, dict) for item in v):
                resolved[k] = [_resolve_colors(item, palettes) for item in v]
            elif all(isinstance(c, list) for c in v):
                resolved[k] = [tuple(c) for c in v]
            else:
                resolved[k] = v
        elif isinstance(v, dict):
            resolved[k] = _resolve_colors(v, palettes)
        else:
            resolved[k] = v
    return resolved


def _create_viewer(entry, config, palettes):
    """Instantiate a viewer from its JSON entry."""
    cls = VIEWER_CLASSES[entry['type']]
    params = dict(entry['params'])

    if 'expand' in entry:
        count = config.getint('PRODUCT', entry['expand'], fallback=0) if config else 0
        params = _expand_viewer_params(params, count, palettes)
    else:
        params = _resolve_colors(params, palettes)

    return cls(**params)


def load_viewers(json_path, config=None):
    """Load viewers from JSON into a list of (key, viewer_instance) tuples."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    palettes = data.get('color_palettes', {})
    result = []
    for entry in data.get('viewers', []):
        viewer = _create_viewer(entry, config, palettes)
        result.append((entry['key'], viewer))
    return result
