"""Automatic LED and buzzer state from sensors and feeder level."""

import math

from django.utils import timezone

from .feeder_level import LOW_FEED_PERCENT, fresh_hopper_percent
from .models import Feeder, SensorReading, Threshold


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
    feeder_percent = None
    feeder_source = None

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

    live_level = fresh_hopper_percent(now)
    if live_level is not None:
        feeder_percent = live_level[0]
        feeder_source = 'ultrasonic'
    else:
        feeder = Feeder.objects.first()
        if feeder and feeder.capacity_max > 0:
            feeder_percent = round(max(0, min(100, feeder.capacity_current / feeder.capacity_max * 100)))
            feeder_source = 'saved estimate'
    feeder_low = feeder_percent is not None and feeder_percent <= LOW_FEED_PERCENT
    if feeder_low:
        issues.append(f'Feeder has {feeder_percent}% feed remaining ({feeder_source}; refill at 15% or less).')

    if disconnected or out_of_range >= 3 or feeder_low:
        color = 'RED'
        reasons = []
        if disconnected:
            reasons.append('A sensor reading is missing or stale.')
        if out_of_range >= 3:
            reasons.append(f'{out_of_range} sensor readings are outside their saved ranges.')
        if feeder_low:
            reasons.append(f'Feeder is at {feeder_percent}% ({feeder_source}), at or below 15%.')
        reason = ' '.join(reasons)
    elif out_of_range:
        color = 'YELLOW'
        reason = f'{out_of_range} sensor reading' + (' is' if out_of_range == 1 else 's are') + ' outside the saved ranges.'
    else:
        color = 'BLUE'
        reason = 'All four sensor readings are within their saved ranges.'

    return {
        'color': color,
        'buzzer': 'ON' if color == 'RED' else 'OFF',
        'reason': reason,
        'issues': issues,
        'out_of_range_count': out_of_range,
        'feeder_percent': feeder_percent,
        'feeder_source': feeder_source,
    }
