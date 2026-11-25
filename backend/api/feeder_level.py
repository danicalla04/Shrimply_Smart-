"""Shared hopper level conversion for alerts and automatic hardware status."""

import math

from django.utils import timezone


HOPPER_FULL_CM = 20.0
HOPPER_TEN_PERCENT_CM = 32.0
LOW_FEED_PERCENT = 15.0
TELEMETRY_MAX_AGE_SECONDS = 20


def hopper_percent(distance_cm):
    try:
        distance = float(distance_cm)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(distance) or distance < 0:
        return None
    percent = 100 + (distance - HOPPER_FULL_CM) * (10 - 100) / (HOPPER_TEN_PERCENT_CM - HOPPER_FULL_CM)
    return max(0, min(100, round(percent)))


def fresh_hopper_percent(now=None):
    from .models import FeederTelemetry

    now = now or timezone.now()
    latest = FeederTelemetry.objects.filter(distance_cm__isnull=False).order_by('-timestamp').first()
    if latest is None or latest.timestamp is None:
        return None
    age = (now - latest.timestamp).total_seconds()
    if not -5 <= age <= TELEMETRY_MAX_AGE_SECONDS:
        return None
    percent = hopper_percent(latest.distance_cm)
    return (percent, latest) if percent is not None else None
