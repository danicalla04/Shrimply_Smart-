import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import FeederTelemetry

logger = logging.getLogger(__name__)


@receiver(post_save, sender=FeederTelemetry)
def broadcast_feeder_telemetry(sender, instance: FeederTelemetry, created: bool, **kwargs):
    """Broadcast new feeder telemetry to ws/feeder/ subscribers."""

    if not created:
        return

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    payload = {
        'id': instance.id,
        'timestamp': instance.timestamp.isoformat() if instance.timestamp else None,
        'motor_state': instance.motor_state,
        'distance_cm': instance.distance_cm,
        'device_id': instance.device_id,
    }

    try:
        async_to_sync(channel_layer.group_send)(
            'feeder_updates',
            {
                'type': 'feeder_telemetry',
                'data': payload,
            },
        )
    except Exception as e:
        logger.warning('[WS_FEEDER] Failed to broadcast telemetry: %s', str(e), exc_info=True)
