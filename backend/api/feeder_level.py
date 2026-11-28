"""Shared hopper level conversion for alerts and automatic hardware status."""

import math
from types import SimpleNamespace

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .feeder_live import LIVE_MAX_AGE_SECONDS, latest_feeder_sample
from .models import Feeder


HOPPER_FULL_CM = 5.0
DEFAULT_HOPPER_EMPTY_CM = 43.5
LOW_FEED_PERCENT = 15.0
TELEMETRY_MAX_AGE_SECONDS = LIVE_MAX_AGE_SECONDS


def hopper_percent(distance_cm, empty_distance_cm=None):
    try:
        distance = float(distance_cm)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(distance) or distance < 0:
        return None
    if empty_distance_cm is None:
        feeder = Feeder.objects.first()
        empty_distance_cm = feeder.hopper_empty_distance_cm if feeder else DEFAULT_HOPPER_EMPTY_CM
    try:
        empty_distance_cm = float(empty_distance_cm)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(empty_distance_cm) or empty_distance_cm <= HOPPER_FULL_CM:
        return None
    percent = (empty_distance_cm - distance) * 100 / (empty_distance_cm - HOPPER_FULL_CM)
    return max(0, min(100, round(percent)))


def fresh_hopper_percent(now=None):
    now = now or timezone.now()
    sample = latest_feeder_sample(now)
    if sample is None:
        return None
    percent = hopper_percent(sample['distance_cm'])
    timestamp = parse_datetime(sample['timestamp'])
    latest = SimpleNamespace(distance_cm=sample['distance_cm'], timestamp=timestamp)
    return (percent, latest) if percent is not None else None
