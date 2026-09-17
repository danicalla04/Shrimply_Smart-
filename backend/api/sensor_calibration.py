"""Apply website-configured calibration to raw sensor readings.

Formula: adjusted = (raw * scale) + offset
Configured in Settings → Sensor Data Adjustment (stored in SensorCalibration).
"""

from typing import Optional

DEFAULT_CALIBRATION = {
    'temperature': {'scale': 1.0, 'offset': 0.0, 'unit': '°C'},
    'ph': {'scale': 1.0, 'offset': 0.0, 'unit': ''},
    'turbidity': {'scale': 1.0, 'offset': 0.0, 'unit': 'NTU'},
    'tds': {'scale': 1.0, 'offset': 0.0, 'unit': 'ppm'},
}


def get_calibration_dict():
    """Return {parameter: {scale, offset, unit}} merged with defaults."""
    from .models import SensorCalibration

    merged = {k: dict(v) for k, v in DEFAULT_CALIBRATION.items()}
    for row in SensorCalibration.objects.all():
        merged[row.parameter] = {
            'scale': float(row.scale),
            'offset': float(row.offset),
            'unit': row.unit or merged.get(row.parameter, {}).get('unit', ''),
        }
    return merged


def apply_calibration_value(parameter: str, raw_value, cal: Optional[dict] = None):
    if raw_value is None:
        return None
    if cal is None:
        cal = get_calibration_dict()
    cfg = cal.get(parameter) or DEFAULT_CALIBRATION.get(parameter, {'scale': 1.0, 'offset': 0.0})
    scale = float(cfg.get('scale', 1.0))
    offset = float(cfg.get('offset', 0.0))
    adjusted = (float(raw_value) * scale) + offset
    if parameter == 'tds':
        return int(round(adjusted))
    return round(adjusted, 2)


def apply_calibration_to_reading(reading, cal: Optional[dict] = None):
    """Return dict of calibrated fields (does not mutate DB row)."""
    if reading is None:
        return None
    if cal is None:
        cal = get_calibration_dict()
    return {
        'id': getattr(reading, 'id', None),
        'temperature': apply_calibration_value('temperature', reading.temperature, cal),
        'ph': apply_calibration_value('ph', reading.ph, cal),
        'turbidity': apply_calibration_value('turbidity', reading.turbidity, cal),
        'tds': apply_calibration_value('tds', reading.tds, cal),
        'timestamp': reading.timestamp.isoformat() if reading.timestamp else None,
    }
