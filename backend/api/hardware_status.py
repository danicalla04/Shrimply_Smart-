"""One LED color and buzzer state from saved ranges and fresh device readings."""

import math

from django.utils import timezone

from .models import Feeder, FeederTelemetry, HardwareTestState, SensorReading, Threshold


DEFAULT_RANGES = {
    'temperature': (25.0, 30.0),
    'ph': (6.5, 8.5),
    'turbidity': (1.0, 25.0),
    'tds': (20.0, 325.0),
}
SENSOR_MAX_AGE_SECONDS = 30
FEEDER_MAX_AGE_SECONDS = 20


def hopper_percent(distance_cm):
    # Same map as frontend/src/services/feeder.js: 20 cm full, 32 cm 10%.
    return max(0, min(100, round(100 + (distance_cm - 20) * (10 - 100) / (32 - 20))))


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
        issues.append('Sensor stream is disconnected or stale')
    else:
        configured = {item.parameter: item for item in Threshold.objects.filter(parameter__in=DEFAULT_RANGES)}
        for parameter, fallback in DEFAULT_RANGES.items():
            value = getattr(reading, parameter)
            if value is None or not math.isfinite(value):
                disconnected = True
                issues.append(f'{parameter} sensor is disconnected')
                continue
            threshold = configured.get(parameter)
            minimum, maximum = (threshold.min_value, threshold.max_value) if threshold else fallback
            if value < minimum or value > maximum:
                out_of_range += 1
                issues.append(f'{parameter} is outside its saved range')

    test_state = HardwareTestState.objects.filter(pk=1).first()
    feeder_test_connected = bool(test_state and test_state.feeder_connected_until and test_state.feeder_connected_until > now)
    feeder = Feeder.objects.first()
    low_limit = feeder.low_percent if feeder else 15
    feeder_percent = None

    if feeder_test_connected:
        feeder_percent = 100  # Test connection assumes a full hopper; no real feeder data is changed.
    else:
        telemetry = FeederTelemetry.objects.filter(device_id='wemos-feeder').first()
        if not telemetry or not fresh(telemetry.timestamp, now, FEEDER_MAX_AGE_SECONDS):
            disconnected = True
            issues.append('Feeder is disconnected or stale')
        elif telemetry.distance_cm is None or not math.isfinite(telemetry.distance_cm):
            disconnected = True
            issues.append('Feeder distance sensor is disconnected')
        else:
            feeder_percent = hopper_percent(telemetry.distance_cm)

    if feeder_percent is not None and feeder_percent <= low_limit:
        issues.append(f'Feeder capacity is low ({feeder_percent}%)')

    if disconnected or out_of_range == len(DEFAULT_RANGES):
        color = 'RED'
    elif out_of_range or (feeder_percent is not None and feeder_percent <= low_limit):
        color = 'YELLOW'
    else:
        color = 'BLUE'

    return {
        'color': color,
        'buzzer': 'OFF' if color == 'BLUE' else 'ON',
        'issues': issues,
        'out_of_range_count': out_of_range,
        'feeder_connected': feeder_test_connected or (feeder_percent is not None),
        'feeder_test_connected': feeder_test_connected,
        'feeder_capacity_percent': feeder_percent,
    }
