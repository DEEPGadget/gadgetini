"""Threshold 비교 → alarm_<항목> Redis 키 SET/DEL.

알람 검사는 제어 명령을 생성하지 않음 — UI 표시·이력 전용.
키 이름은 sensor_exporter / Grafana 측이 직접 참조.
"""
import logging

from . import redis_keys as K

log = logging.getLogger(__name__)


# 연속 수치형 임계 (warning_below/above + critical_below/above)
_CONTINUOUS = (
    'coolant_temp_inlet',
    'coolant_temp_outlet',
    'coolant_delta_t',
    'ambient_temp',
    'ambient_humidity',
)


def check_all(rd, thresholds_cfg):
    pipe = rd.pipeline(transaction=False)

    # 1) 연속 수치형 — 각 spec.keys 마다 동일 임계로 평가
    for spec_name in _CONTINUOUS:
        spec = thresholds_cfg.get(spec_name)
        if not spec:
            continue
        for rkey in spec.get('keys', []):
            v = _get_float(rd, rkey)
            warn, crit = _eval_continuous(v, spec)
            # 알람 키 이름은 spec_name을 그대로 사용 (예: alarm_coolant_temp_outlet_warning)
            _set_alarm(pipe, f'{spec_name}_warning', warn)
            _set_alarm(pipe, f'{spec_name}_critical', crit)

    # 2) 수위 — 단일 센서 0/1 (active-high: 1=정상, 0=LOW=critical)
    spec = thresholds_cfg.get('coolant_level') or {}
    v = _get_int(rd, K.COOLANT_LEVEL)
    if v is not None:
        warn_at = spec.get('warning_at')
        crit_at = spec.get('critical_at')
        _set_alarm(pipe, 'water_level_warning', warn_at is not None and v == warn_at)
        _set_alarm(pipe, 'water_level_critical', crit_at is not None and v == crit_at)

    # 3) 누수 — 1 = LEAKED → critical
    spec = thresholds_cfg.get('coolant_leak') or {}
    v = _get_int(rd, K.COOLANT_LEAK)
    if v is not None:
        crit_at = spec.get('critical_at')
        _set_alarm(pipe, 'leak_detected', crit_at is not None and v == crit_at)

    pipe.execute()


def _get_float(rd, key):
    raw = rd.get(key)
    if raw is None:
        return None
    try: return float(raw)
    except (TypeError, ValueError): return None


def _get_int(rd, key):
    raw = rd.get(key)
    if raw is None:
        return None
    try: return int(float(raw))
    except (TypeError, ValueError): return None


def _eval_continuous(v, spec):
    """Return (warning_active, critical_active)."""
    if v is None:
        return (False, False)
    crit = (
        ('critical_below' in spec and v < spec['critical_below']) or
        ('critical_above' in spec and v > spec['critical_above'])
    )
    warn = (
        ('warning_below' in spec and v < spec['warning_below']) or
        ('warning_above' in spec and v > spec['warning_above'])
    )
    return (warn, crit)


def _set_alarm(pipe, name, active):
    rkey = K.alarm(name)
    if active:
        pipe.set(rkey, 1)
    else:
        pipe.delete(rkey)
