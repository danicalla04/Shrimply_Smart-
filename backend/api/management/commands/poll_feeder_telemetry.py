import time

import requests
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from api.models import Alert, FeederTelemetry, SensorReading, Threshold
from api.feeder_servo_scheduler import process_servo_schedule_tick, ensure_next_servo_job_seeded


def _create_and_broadcast_alert(*, parameter: str, severity: str, value: float, threshold_min: float, threshold_max: float, message: str):
    cutoff = timezone.now() - timedelta(hours=1)
    if Alert.objects.filter(parameter=parameter, severity=severity, resolved=False, timestamp__gte=cutoff).exists():
        return None

    alert = Alert.objects.create(
        parameter=parameter,
        severity=severity,
        value=float(value),
        threshold_min=float(threshold_min),
        threshold_max=float(threshold_max),
        message=str(message),
        timestamp=timezone.now(),
    )

    channel_layer = get_channel_layer()
    if channel_layer is not None:
        payload = {
            'id': alert.id,
            'parameter': alert.parameter,
            'severity': alert.severity,
            'value': alert.value,
            'threshold_min': alert.threshold_min,
            'threshold_max': alert.threshold_max,
            'message': alert.message,
            'timestamp': alert.timestamp.isoformat(),
            'resolved': alert.resolved,
        }
        try:
            async_to_sync(channel_layer.group_send)(
                'alert_updates',
                {
                    'type': 'alert_notification',
                    'data': {
                        'event': 'new_alert',
                        'alert': payload,
                    },
                },
            )
        except Exception:
            # Don't crash poller if websocket push fails.
            pass

    return alert


class Command(BaseCommand):
    help = "Poll the WeMos/ESP feeder status endpoint and store telemetry for WebSocket push."  # noqa: A003

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval",
            type=float,
            default=6.0,
            help="Polling interval in seconds (default: 6.0)",
        )
        parser.add_argument(
            "--path",
            type=str,
            default="/api/status",
            help="Device path to poll (default: /api/status)",
        )
        parser.add_argument(
            "--device-id",
            type=str,
            default="wemos-poller",
            help="device_id value to store with telemetry",
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=None,
            help="HTTP timeout seconds (defaults to WEMOS_PROXY_TIMEOUT_SEC)",
        )

        parser.add_argument(
            "--enable-servo-scheduler",
            action="store_true",
            help="Also process scheduled servo ON/OFF using api_feedertelemetry.on_at/off_at",
        )
        parser.add_argument(
            "--schedule-interval",
            type=float,
            default=0.5,
            help="Servo scheduler check interval in seconds (default: 0.5)",
        )

    def handle(self, *args, **options):
        interval = float(options["interval"])
        path = str(options["path"])
        device_id = str(options["device_id"])
        timeout = options["timeout"]
        enable_servo_scheduler = bool(options.get("enable_servo_scheduler"))
        schedule_interval = float(options.get("schedule_interval") or 0.5)
        if timeout is None:
            timeout = float(getattr(settings, "WEMOS_PROXY_TIMEOUT_SEC", 2.0))

        base = str(getattr(settings, "WEMOS_BASE_URL", "")).rstrip("/")
        if not base:
            self.stderr.write(self.style.ERROR("WEMOS_BASE_URL is not configured"))
            return

        if not path.startswith("/"):
            path = "/" + path

        url = base + path
        self.stdout.write(self.style.SUCCESS(f"Polling feeder telemetry from {url} every {interval}s"))
        if enable_servo_scheduler:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Servo scheduler enabled (checks every {schedule_interval}s; device_id={device_id})"
                )
            )

        try:
            next_poll_at = time.monotonic()
            next_schedule_at = time.monotonic()
            next_seed_at = time.monotonic()
            last_poll_ok = True

            while True:
                try:
                    now_mono = time.monotonic()

                    # Servo scheduler tick (fast cadence)
                    if enable_servo_scheduler and now_mono >= next_schedule_at:
                        next_schedule_at = now_mono + max(0.1, schedule_interval)
                        tick = process_servo_schedule_tick(device_id=device_id, timeout=timeout)
                        if tick.started_job_id is not None:
                            self.stdout.write(self.style.SUCCESS(f"[SERVO] START job_id={tick.started_job_id}"))
                        if tick.stopped_job_id is not None:
                            self.stdout.write(self.style.SUCCESS(f"[SERVO] STOP job_id={tick.stopped_job_id}"))
                        if tick.error:
                            self.stderr.write(f"[SERVO] {tick.error}")

                    # Keep one future scheduled job seeded from Feeder settings
                    if enable_servo_scheduler and now_mono >= next_seed_at:
                        next_seed_at = now_mono + 5.0
                        seeded_id = ensure_next_servo_job_seeded(device_id=device_id)
                        if seeded_id is not None:
                            self.stdout.write(self.style.SUCCESS(f"[SERVO] SEEDED job_id={seeded_id}"))

                    # Telemetry poll (slower cadence)
                    if now_mono >= next_poll_at:
                        next_poll_at = now_mono + max(0.5, interval)

                        resp = None
                        data = {}
                        try:
                            resp = requests.get(url, timeout=timeout)
                            if resp.ok and resp.headers.get("content-type", "").startswith("application/json"):
                                data = resp.json()
                        except Exception as req_err:
                            resp = None
                            self.stderr.write(f"Poll request error: {req_err}")

                        if resp is None or not resp.ok:
                            if resp is not None:
                                self.stderr.write(f"HTTP {resp.status_code}: {(resp.text or '')[:200]}")

                            _create_and_broadcast_alert(
                                parameter='feeder_connection',
                                severity='critical',
                                value=0.0,
                                threshold_min=1.0,
                                threshold_max=1.0,
                                message='Feeder device disconnected or unreachable.',
                            )
                            last_poll_ok = False
                        else:
                            if not last_poll_ok:
                                # Mark previous connection alerts resolved when device is reachable again.
                                Alert.objects.filter(parameter='feeder_connection', resolved=False).update(resolved=True)
                            last_poll_ok = True

                            # If the device includes full sensor payload in `/api/status`, persist it too.
                            # This allows laptop-side polling to populate the SensorReading table without
                            # requiring ESP->PC inbound firewall rules.
                            try:
                                temp_val = data.get("temperature")
                                ph_val = data.get("ph")
                                tds_val = data.get("tds")
                                turb_val = data.get("turbidity")
                                if (
                                    temp_val is not None
                                    and ph_val is not None
                                    and tds_val is not None
                                    and turb_val is not None
                                ):
                                    reading = SensorReading.objects.create(
                                        temperature=float(temp_val),
                                        ph=float(ph_val),
                                        tds=int(float(tds_val)),
                                        turbidity=float(turb_val),
                                    )

                                    # Match the lightweight alert checks used by /api/update-sensors/
                                    required_fields = ["temperature", "ph", "turbidity", "tds"]
                                    thresholds = {t.parameter: t for t in Threshold.objects.all()}
                                    for param in required_fields:
                                        if param not in thresholds:
                                            continue
                                        threshold = thresholds[param]
                                        value = getattr(reading, param, None)
                                        if value is None:
                                            continue

                                        if value < threshold.min_value:
                                            Alert.objects.create(
                                                parameter=param,
                                                severity="low",
                                                value=value,
                                                threshold_min=threshold.min_value,
                                                threshold_max=threshold.max_value,
                                                message=(
                                                    f"{param} is below minimum threshold "
                                                    f"({value} < {threshold.min_value})"
                                                ),
                                            )
                                        elif value > threshold.max_value:
                                            Alert.objects.create(
                                                parameter=param,
                                                severity="high",
                                                value=value,
                                                threshold_min=threshold.min_value,
                                                threshold_max=threshold.max_value,
                                                message=(
                                                    f"{param} is above maximum threshold "
                                                    f"({value} > {threshold.max_value})"
                                                ),
                                            )

                                    # Broadcast to ws/sensors/ subscribers (same shape as update_sensors)
                                    channel_layer = get_channel_layer()
                                    if channel_layer is not None:
                                        async_to_sync(channel_layer.group_send)(
                                            "sensor_updates",
                                            {
                                                "type": "sensor_reading",
                                                "data": {
                                                    "temperature": float(reading.temperature),
                                                    "ph": float(reading.ph),
                                                    "turbidity": float(reading.turbidity),
                                                    "tds": int(reading.tds),
                                                    "timestamp": reading.timestamp.isoformat(),
                                                },
                                            },
                                        )
                            except Exception as sensor_err:
                                self.stderr.write(f"Sensor save error: {sensor_err}")

                            motor_state = (
                                str(data.get("motor_state") or data.get("motor") or "")
                                .strip()
                                .upper()
                            )
                            distance_val = data.get("distance_cm")
                            if distance_val is None:
                                distance_val = data.get("distance")

                            distance_cm = None
                            if distance_val is not None and distance_val != "null" and distance_val != "":
                                try:
                                    distance_cm = float(distance_val)
                                except Exception:
                                    distance_cm = None

                            telemetry = FeederTelemetry.objects.create(
                                motor_state=motor_state,
                                distance_cm=distance_cm,
                                device_id=device_id,
                            )
                            self.stdout.write(
                                f"Saved telemetry id={telemetry.id} motor={motor_state} distance={distance_cm}"
                            )
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    self.stderr.write(f"Poll error: {e}")

                time.sleep(0.2)
        except KeyboardInterrupt:
            self.stdout.write("Stopped.")
