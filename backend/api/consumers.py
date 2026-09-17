"""
WebSocket consumer for real-time sensor data push and alert notifications.

Clients connect to:
- ws://<host>/ws/sensors/ for live sensor readings
- ws://<host>/ws/alerts/ for real-time alert updates
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger('websocket')


class SensorConsumer(AsyncWebsocketConsumer):
    """Broadcasts live sensor readings to all connected dashboard clients."""

    GROUP_NAME = "sensor_updates"

    async def connect(self):
        logger.info(f'[WS_SENSOR] Client connected: {self.channel_name}')
        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()
        logger.debug(f'[WS_SENSOR] Added to group: {self.GROUP_NAME}')

    async def disconnect(self, close_code):
        logger.info(f'[WS_SENSOR] Client disconnected: {self.channel_name} (code: {close_code})')
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Clients don't send data; ignore any incoming messages.
        if text_data:
            logger.debug(f'[WS_SENSOR] Ignoring client message: {text_data[:50]}...')

    # ---- Custom event handler called via group_send ----
    async def sensor_reading(self, event):
        """Push a new sensor reading to the WebSocket client."""
        try:
            reading_data = event.get("data", {})
            logger.debug(f'[WS_SENSOR] Sending sensor reading to {self.channel_name}')
            await self.send(text_data=json.dumps(reading_data))
        except Exception as e:
            logger.error(f'[WS_SENSOR] Failed to send message: {str(e)}', exc_info=True)


class AlertConsumer(AsyncWebsocketConsumer):
    """Broadcasts alert notifications to all connected clients in real-time."""

    GROUP_NAME = "alert_updates"

    async def connect(self):
        logger.info(f'[WS_ALERT] Client connected: {self.channel_name}')
        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()
        logger.debug(f'[WS_ALERT] Added to group: {self.GROUP_NAME}')

    async def disconnect(self, close_code):
        logger.info(f'[WS_ALERT] Client disconnected: {self.channel_name} (code: {close_code})')
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Clients don't send data; ignore any incoming messages.
        if text_data:
            logger.debug(f'[WS_ALERT] Ignoring client message: {text_data[:50]}...')

    # ---- Custom event handler called via group_send ----
    async def alert_notification(self, event):
        """Push a new alert to the WebSocket client."""
        try:
            alert_data = event.get("data", {})
            event_type = alert_data.get("event", "unknown")
            logger.debug(f'[WS_ALERT] Broadcasting {event_type} to {self.channel_name}')
            
            # Log alert details if available
            alert_info = alert_data.get("alert", {})
            if alert_info:
                logger.debug(f'[WS_ALERT] Alert ID: {alert_info.get("id")}, Severity: {alert_info.get("severity")}, Param: {alert_info.get("parameter")}')
            
            await self.send(text_data=json.dumps(alert_data))
            logger.debug(f'[WS_ALERT] Successfully sent {event_type} to {self.channel_name}')
        except Exception as e:
            logger.error(f'[WS_ALERT] Failed to send alert: {str(e)}', exc_info=True)


class FeederConsumer(AsyncWebsocketConsumer):
    """Broadcasts feeder telemetry (motor state + ultrasonic distance) to all connected clients."""

    GROUP_NAME = "feeder_updates"

    async def connect(self):
        logger.info(f'[WS_FEEDER] Client connected: {self.channel_name}')
        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()
        logger.debug(f'[WS_FEEDER] Added to group: {self.GROUP_NAME}')

        try:
            latest = await self._get_latest_telemetry()
            if latest:
                await self.send(text_data=json.dumps(latest))
        except Exception as e:
            logger.error(f'[WS_FEEDER] Failed to send initial telemetry: {str(e)}', exc_info=True)

    async def disconnect(self, close_code):
        logger.info(f'[WS_FEEDER] Client disconnected: {self.channel_name} (code: {close_code})')
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Clients don't send data; ignore any incoming messages.
        if text_data:
            logger.debug(f'[WS_FEEDER] Ignoring client message: {text_data[:50]}...')

    async def feeder_telemetry(self, event):
        """Push a new feeder telemetry message to the WebSocket client."""
        try:
            payload = event.get("data", {})
            await self.send(text_data=json.dumps(payload))
        except Exception as e:
            logger.error(f'[WS_FEEDER] Failed to send telemetry: {str(e)}', exc_info=True)

    @database_sync_to_async
    def _get_latest_telemetry(self):
        from .models import FeederTelemetry

        latest = FeederTelemetry.objects.order_by('-timestamp').first()
        if not latest:
            return None

        return {
            'id': latest.id,
            'timestamp': latest.timestamp.isoformat() if latest.timestamp else None,
            'motor_state': latest.motor_state,
            'distance_cm': latest.distance_cm,
            'device_id': latest.device_id,
        }
