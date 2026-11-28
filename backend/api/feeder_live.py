"""One-minute live feeder readings with seven-minute history snapshots."""

from django.core.cache import caches
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import FeederTelemetry


HISTORY_INTERVAL_SECONDS = 7 * 60
LIVE_MAX_AGE_SECONDS = 150
LIVE_CACHE_SECONDS = 180
LIVE_CACHE_KEY = 'latest_feeder_distance_v1'


def _sample_age_seconds(sample, now):
    timestamp = parse_datetime(str(sample.get('timestamp') or ''))
    if timestamp is None:
        return None
    if timezone.is_naive(timestamp):
        timestamp = timezone.make_aware(timestamp)
    return (now - timestamp).total_seconds()


def latest_live_sample(now=None):
    now = now or timezone.now()
    sample = caches['feeder_live'].get(LIVE_CACHE_KEY)
    if not isinstance(sample, dict):
        return None
    age = _sample_age_seconds(sample, now)
    return sample if age is not None and -5 <= age <= LIVE_MAX_AGE_SECONDS else None


def latest_feeder_sample(now=None):
    """Return a fresh live reading, falling back to a recent history row."""
    now = now or timezone.now()
    live = latest_live_sample(now)
    if live is not None:
        return live
    last = FeederTelemetry.objects.filter(distance_cm__isnull=False).order_by('-timestamp').first()
    if last is None or last.timestamp is None:
        return None
    age = (now - last.timestamp).total_seconds()
    if not -5 <= age <= LIVE_MAX_AGE_SECONDS:
        return None
    return {
        'id': last.pk,
        'timestamp': last.timestamp.isoformat(),
        'distance_cm': last.distance_cm,
        'motor_state': last.motor_state,
        'device_id': last.device_id,
        'source': 'history',
    }


def record_feeder_sample(*, distance_cm, motor_state='', device_id='wemos-feeder', now=None):
    """Update the shared live value; append history only every seven minutes."""
    now = now or timezone.now()
    if distance_cm is None:
        return None, False
    sample = {
        'timestamp': now.isoformat(),
        'distance_cm': float(distance_cm),
        'motor_state': str(motor_state or '')[:10],
        'device_id': str(device_id or 'wemos-feeder')[:64],
        'source': 'live',
    }
    caches['feeder_live'].set(LIVE_CACHE_KEY, sample, LIVE_CACHE_SECONDS)

    last = FeederTelemetry.objects.filter(device_id=sample['device_id'], distance_cm__isnull=False).order_by('-timestamp').first()
    should_save = last is None or (now - last.timestamp).total_seconds() >= HISTORY_INTERVAL_SECONDS
    if should_save:
        row = FeederTelemetry.objects.create(
            motor_state=sample['motor_state'],
            distance_cm=sample['distance_cm'],
            device_id=sample['device_id'],
        )
        sample['id'] = row.pk
    return sample, should_save
