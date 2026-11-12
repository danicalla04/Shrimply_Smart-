"""LED and buzzer state determined only by fresh sensor readings and saved ranges."""

import math

from django.utils import timezone

from .models import SensorReading, Threshold


DEFAULT_RANGES = {
    'temperature': (25.0, 30.0),
    'ph': (6.5, 8.5),
    'turbidity': (1.0, 25.0),
    'tds': (20.0, 325.0),
}
SENSOR_LABELS = {'temperature': 'Temperature', 'ph': 'pH', 'turbidity': 'Turbidity', 'tds': 'TDS'}
SENSOR_MAX_AGE_SECONDS = 30


def fresh(timestamp, now, max_age):
    if timestamp is None:
        return False
    age = (now - timestamp).total_seconds()
    return -5 <= age <= max_age


def assess_hardware_status(now=None):
    now = now or timezone.now()
    issues = []
    disconnected = False
    out_of_range = 0

    reading = SensorReading.objects.first()
    if not reading or not fresh(reading.timestamp, now, SENSOR_MAX_AGE_SECONDS):
        disconnected = True
        issues.append('Sensor readings are missing or older than 30 seconds.')
    else:
        configured = {item.parameter: item for item in Threshold.objects.filter(parameter__in=DEFAULT_RANGES)}
        for parameter, fallback in DEFAULT_RANGES.items():
            value = getattr(reading, parameter)
            if value is None or not math.isfinite(value):
                disconnected = True
                issues.append(f'{SENSOR_LABELS[parameter]} reading is missing.')
                continue
            threshold = configured.get(parameter)
            minimum, maximum = (threshold.min_value, threshold.max_value) if threshold else fallback
            if value < minimum or value > maximum:
                out_of_range += 1
                issues.append(f'{SENSOR_LABELS[parameter]} {value:g} is outside {minimum:g} to {maximum:g}.')

    if disconnected or out_of_range == len(DEFAULT_RANGES):
        color = 'RED'
        reason = ('A sensor reading is missing or stale.' if disconnected else
                  'All four sensor readings are outside their saved ranges.')
    elif out_of_range:
        color = 'YELLOW'
        reason = f'{out_of_range} sensor reading' + (' is' if out_of_range == 1 else 's are') + ' outside the saved ranges.'
    else:
        color = 'BLUE'
        reason = 'All four sensor readings are within their saved ranges.'

    return {
        'color': color,
        'buzzer': 'OFF' if color == 'BLUE' else 'ON',
        'reason': reason,
        'issues': issues,
        'out_of_range_count': out_of_range,
    }
