"""
Alert Service for Water Quality Monitoring
Checks sensor readings against thresholds and generates alerts
Also detects disconnected sensors (NULL readings) and emails notification_email.
"""

from django.utils import timezone
from django.db.models import Q
from django.core.mail import send_mail
from django.core.cache import cache
from django.conf import settings
from .models import Alert, Threshold, SensorReading, HistorySettings
from datetime import timedelta
import logging
import threading
import time

# Create a dedicated logger for alert service
logger = logging.getLogger('alert_service')
logger.setLevel(logging.DEBUG)

# Add console handler if not already present
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class AlertService:
    """Service for generating and managing water quality alerts"""
    
    # Alert thresholds (beyond min/max, trigger alerts)
    CRITICAL_THRESHOLD_PERCENT = 0.15  # 15% beyond threshold triggers critical alert
    WARNING_THRESHOLD_PERCENT = 0.10   # 10% beyond threshold triggers warning
    
    # Parameters that decrease when they drop (oxygen, pH)
    DECREASING_PARAMS = ['oxygen', 'ph']
    # Parameters that increase when they spike (temperature, tds, ec)
    INCREASING_PARAMS = ['temperature', 'tds', 'ec']
    
    @staticmethod
    def check_reading_and_create_alerts(sensor_reading):
        """Check a single sensor reading against thresholds and create alerts if needed"""
        start_time = time.time()
        logger.info(f'═══════════════════════════════════════════════════════════')
        logger.info(f'[ALERT_CHECK] Starting alert check for reading #{sensor_reading.id}')
        logger.info(f'[READING_TIME] {sensor_reading.timestamp.isoformat()}')
        logger.debug(f'  ├─ Temperature: {sensor_reading.temperature}°C')
        logger.debug(f'  ├─ pH: {sensor_reading.ph}')
        logger.debug(f'  ├─ Turbidity: {sensor_reading.turbidity} NTU')
        logger.debug(f'  └─ TDS: {sensor_reading.tds} ppm')
        
        created_alerts = []
        thresholds = Threshold.objects.all()
        
        if not thresholds.exists():
            logger.warning('[ALERT_CHECK] ⚠️  NO THRESHOLDS SET UP - Skipping alert check')
            return created_alerts
        
        logger.debug(f'[THRESHOLDS] Found {thresholds.count()} configured thresholds')
        
        for idx, threshold in enumerate(thresholds, 1):
            param = threshold.parameter
            value = getattr(sensor_reading, param, None)
            
            logger.debug(f'  [{idx}/{thresholds.count()}] Checking {param}:')
            logger.debug(f'      Value: {value} | Range: {threshold.min_value}-{threshold.max_value} {threshold.unit}')
            
            if value is None or value <= 0:
                logger.debug(f'      ⊘ Skipped: Invalid value (None or ≤0)')
                continue
            
            # Check if reading is outside acceptable range
            alert = AlertService.evaluate_parameter(
                param=param,
                value=value,
                threshold=threshold,
                sensor_reading=sensor_reading
            )
            
            if alert:
                created_alerts.append(alert)
                logger.warning(f'      ✅ ALERT CREATED: {alert.severity.upper()} - {alert.parameter.upper()} = {alert.value}')
            else:
                logger.debug(f'      ▪ OK: Within acceptable range')
        
        elapsed_time = time.time() - start_time
        logger.info(f'[ALERT_CHECK] ✓ Completed: {len(created_alerts)} alerts created in {elapsed_time:.3f}s')
        logger.info(f'═══════════════════════════════════════════════════════════')
        return created_alerts
    
    @staticmethod
    def evaluate_parameter(param, value, threshold, sensor_reading):
        """Evaluate a single parameter against its threshold"""
        min_val = threshold.min_value
        max_val = threshold.max_value
        unit = threshold.unit or ''
        
        # Calculate critical and warning boundaries
        param_range = max_val - min_val
        critical_margin = param_range * AlertService.CRITICAL_THRESHOLD_PERCENT
        warning_margin = param_range * AlertService.WARNING_THRESHOLD_PERCENT
        
        critical_min = min_val - critical_margin
        critical_max = max_val + critical_margin
        warning_min = min_val - warning_margin
        warning_max = max_val + warning_margin
        
        logger.debug(f'        Range: {min_val}-{max_val} {unit}')
        logger.debug(f'        Warning Zone: {warning_min:.2f}-{warning_max:.2f} {unit}')
        logger.debug(f'        Critical Zone: {critical_min:.2f}-{critical_max:.2f} {unit}')
        
        # Determine severity
        severity = None
        message = None
        
        if value < critical_min or value > critical_max:
            severity = 'critical'
            logger.debug(f'        Status: 🔴 CRITICAL (outside {critical_min:.2f}-{critical_max:.2f})')
        elif value < warning_min or value > warning_max:
            severity = 'warning'
            logger.debug(f'        Status: 🟡 WARNING (outside {warning_min:.2f}-{warning_max:.2f})')
        elif value < min_val or value > max_val:
            severity = 'warning'
            logger.debug(f'        Status: 🟡 WARNING (outside optimal {min_val}-{max_val})')
        
        if severity is None:
            logger.debug(f'        Status: 🟢 OK (within range)')
            return None  # No alert needed
        
        # Generate message
        if param in AlertService.DECREASING_PARAMS:
            if value < min_val:
                message = f"{param.upper()} CRITICAL LOW: {value:.2f}{unit} (minimum: {min_val}{unit})"
        else:  # INCREASING_PARAMS
            if value > max_val:
                message = f"{param.upper()} CRITICAL HIGH: {value:.2f}{unit} (maximum: {max_val}{unit})"
        
        if not message:
            if value < min_val:
                message = f"{param.upper()} below threshold: {value:.2f}{unit} < {min_val}{unit}"
            else:
                message = f"{param.upper()} above threshold: {value:.2f}{unit} > {max_val}{unit}"
        
        logger.debug(f'        Message: {message}')
        
        # One open alert per parameter: if an unresolved alert already exists for
        # this sensor, UPDATE it (refresh timestamp/severity/value/message) instead
        # of creating a duplicate row. A new row is only created after the user
        # marks the previous one as read (resolved=True).
        existing_alert = Alert.objects.filter(
            parameter=param,
            resolved=False,
        ).order_by('-timestamp').first()

        if existing_alert:
            existing_alert.severity = severity
            existing_alert.value = value
            existing_alert.threshold_min = threshold.min_value
            existing_alert.threshold_max = threshold.max_value
            existing_alert.message = message
            existing_alert.timestamp = timezone.now()
            existing_alert.save(update_fields=[
                'severity', 'value', 'threshold_min', 'threshold_max',
                'message', 'timestamp',
            ])
            logger.debug(
                f'        ↻ Refreshed existing open {param} alert '
                f'(ID: {existing_alert.id}) instead of creating a duplicate'
            )
            return None  # Not a "new" alert (no re-broadcast / re-email)

        # Create new alert (safe: no multi-row lookup)
        try:
            alert = Alert.objects.create(
                parameter=param,
                severity=severity,
                value=value,
                threshold_min=threshold.min_value,
                threshold_max=threshold.max_value,
                message=message,
                timestamp=timezone.now(),
            )
            logger.info(f'        ✅ Created {severity.upper()} alert (ID: {alert.id})')
            AlertService.notify_alert_async(alert)
            return alert
        except Exception as e:
            logger.error(f'        ❌ Failed to create alert: {str(e)}', exc_info=True)
            return None
    
    @staticmethod
    def get_active_alerts(limit=10):
        """Get currently active (unresolved) alerts"""
        logger.debug(f'[FETCH_ACTIVE] Retrieving up to {limit} active alerts...')
        alerts = Alert.objects.filter(
            resolved=False,
            timestamp__gte=timezone.now() - timedelta(days=1)
        ).order_by('-timestamp')[:limit]
        logger.debug(f'[FETCH_ACTIVE] Found {alerts.count()} active alerts')
        return alerts
    
    @staticmethod
    def get_alerts_for_parameter(parameter, days=7):
        """Get alerts for a specific parameter in the last N days"""
        logger.debug(f'[FETCH_PARAM_ALERTS] Getting {parameter} alerts from last {days} days...')
        alerts = Alert.objects.filter(
            parameter=parameter,
            timestamp__gte=timezone.now() - timedelta(days=days)
        ).order_by('-timestamp')
        logger.debug(f'[FETCH_PARAM_ALERTS] Found {alerts.count()} {parameter} alerts')
        return alerts
    
    @staticmethod
    def resolve_alert(alert_id):
        """Mark an alert as resolved"""
        logger.debug(f'[RESOLVE_ALERT] Resolving alert ID: {alert_id}')
        try:
            alert = Alert.objects.get(id=alert_id)
            alert.resolved = True
            alert.save()
            logger.info(f'[RESOLVE_ALERT] ✅ Alert {alert_id} marked as resolved')
            return alert
        except Alert.DoesNotExist:
            logger.warning(f'[RESOLVE_ALERT] ⚠️  Alert {alert_id} not found')
            return None
    
    @staticmethod
    def get_alert_summary():
        """Get summary of active alerts by severity"""
        logger.debug(f'[ALERT_SUMMARY] Generating alert summary...')
        active_alerts = Alert.objects.filter(
            resolved=False,
            timestamp__gte=timezone.now() - timedelta(days=1)
        )
        
        critical = active_alerts.filter(severity='critical').count()
        warning = active_alerts.filter(severity='warning').count()
        low = active_alerts.filter(severity='low').count()
        
        summary = {
            'total': active_alerts.count(),
            'critical': critical,
            'warning': warning,
            'low': low,
            'alerts': list(active_alerts.values('id', 'parameter', 'severity', 'value', 'message', 'timestamp'))
        }
        
        logger.info(f'[ALERT_SUMMARY] Total: {summary["total"]} | 🔴 Critical: {critical} | 🟡 Warning: {warning} | 🔵 Low: {low}')
        return summary
    
    @staticmethod
    def cleanup_old_alerts(days=30):
        """Delete alerts older than N days"""
        logger.debug(f'[CLEANUP] Starting cleanup of alerts older than {days} days...')
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count, _ = Alert.objects.filter(
            timestamp__lt=cutoff_date,
            resolved=True
        ).delete()
        logger.info(f'[CLEANUP] ✓ Deleted {deleted_count} old alerts from before {cutoff_date.isoformat()}')
        return deleted_count

    SENSOR_PARAMS = ('temperature', 'ph', 'turbidity', 'tds')
    DISCONNECT_DEDUPE_MINUTES = 30
    # No new reading for this long → treat stream as offline (matches Dashboard UI)
    STALE_READING_SECONDS = 45
    # No feeder telemetry for this long → ultrasonic/feeder device offline
    # (matches the 20s "Telemetry age" threshold used on the Feeding page)
    FEEDER_STALE_SECONDS = 20
    # Larger ultrasonic gap = less feed in the hopper
    FEEDER_LOW_DISTANCE_CM = 32.0
    # After user marks offline/disconnect as read, do not recreate until sensors recover
    _SNOOZE_UNTIL_ONLINE_PREFIX = 'alert:snooze_until_online:'
    _CREATE_LOCK_PREFIX = 'alert:creating:'

    @staticmethod
    def send_alert_email(alert: Alert):
        """Email Settings → notification_email for any new alert (threshold, offline, feeder, etc.)."""
        if getattr(alert, 'email_sent', False):
            return False

        emails = AlertService._notification_emails()
        if not emails:
            logger.info('[ALERT_EMAIL] No notification_email in Settings — skip')
            return False

        when = timezone.localtime(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S')
        label = AlertService._param_label(alert.parameter)
        sev = (alert.severity or 'warning').upper()
        subject = f'[Shrimply Smart] {sev} alert: {label}'
        value_line = (
            f'Value     : {alert.value}\n'
            if alert.value is not None
            else 'Value     : (none / disconnected)\n'
        )
        body = (
            f'Shrimply Smart alert\n\n'
            f'Parameter : {label}\n'
            f'Severity  : {sev}\n'
            f'{value_line}'
            f'Time      : {when}\n'
            f'Message   : {alert.message}\n\n'
            f'Open the Alerts page in the app to acknowledge.\n'
        )
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@shrimplysmart.local'),
                recipient_list=emails,
                fail_silently=False,
            )
            alert.email_sent = True
            alert.save(update_fields=['email_sent'])
            logger.info('[ALERT_EMAIL] Sent to %s for alert #%s (%s)', emails, alert.id, alert.parameter)
            return True
        except Exception as exc:
            logger.error('[ALERT_EMAIL] Failed: %s', exc, exc_info=True)
            return False

    @staticmethod
    def send_disconnect_email(alert: Alert):
        """Back-compat alias — all alerts use send_alert_email now."""
        return AlertService.send_alert_email(alert)

    @staticmethod
    def notify_alert_async(alert: Alert):
        """Fire-and-forget email so API responses stay fast."""
        if alert is None:
            return
        threading.Thread(
            target=AlertService.send_alert_email,
            args=(alert,),
            daemon=True,
        ).start()

    @staticmethod
    def _param_label(param: str) -> str:
        return {
            'temperature': 'Temperature',
            'ph': 'pH',
            'turbidity': 'Turbidity',
            'tds': 'TDS',
            'sensor_offline': 'Sensors Offline',
            'feeder_capacity': 'Feeder Capacity',
            'feeder_connection': 'Ultrasonic / Feeder',
            'feeder_level': 'Feeder Level',
        }.get(param, param)

    @staticmethod
    def snooze_until_online(parameter: str):
        """User acknowledged alert while condition may still be true — wait for recovery."""
        cache.set(
            f'{AlertService._SNOOZE_UNTIL_ONLINE_PREFIX}{parameter}',
            True,
            timeout=60 * 60 * 12,  # auto-expire after 12h as safety net
        )
        logger.info('[DISCONNECT] Snoozed %s until sensors recover', parameter)

    @staticmethod
    def clear_snooze(parameter: str):
        cache.delete(f'{AlertService._SNOOZE_UNTIL_ONLINE_PREFIX}{parameter}')

    @staticmethod
    def is_snoozed(parameter: str) -> bool:
        return bool(cache.get(f'{AlertService._SNOOZE_UNTIL_ONLINE_PREFIX}{parameter}'))

    @staticmethod
    def _notification_emails():
        """Emails from Settings → Notification email (HistorySettings)."""
        emails = []
        for hs in HistorySettings.objects.exclude(notification_email='').exclude(
            notification_email__isnull=True
        ):
            email = (hs.notification_email or '').strip()
            if email and email not in emails:
                emails.append(email)
        return emails

    @staticmethod
    def _create_offline_alert(msg: str):
        """
        Create at most one open sensor_offline alert.
        If the user marked it read while still offline, stay quiet until recovery.
        Uses a short cache lock so concurrent /sensors/latest polls cannot spam rows.
        """
        param = 'sensor_offline'
        if AlertService.is_snoozed(param):
            return None

        open_alert = Alert.objects.filter(
            parameter=param, severity='critical', resolved=False,
        ).first()
        if open_alert:
            # Keep a single open alert; refresh age in the message
            if open_alert.message != msg:
                open_alert.message = msg
                open_alert.save(update_fields=['message'])
            return None

        lock_key = f'{AlertService._CREATE_LOCK_PREFIX}{param}'
        if not cache.add(lock_key, True, timeout=15):
            return None
        alert = None
        try:
            if AlertService.is_snoozed(param):
                return None
            if Alert.objects.filter(parameter=param, severity='critical', resolved=False).exists():
                return None
            alert = Alert.objects.create(
                parameter=param,
                severity='critical',
                value=None,
                threshold_min=0,
                threshold_max=0,
                message=msg,
            )
        finally:
            cache.delete(lock_key)

        if alert is None:
            return None

        AlertService.notify_alert_async(alert)
        logger.warning('[DISCONNECT] %s', msg)
        return alert

    @staticmethod
    def check_feeder_connection():
        """
        Create/refresh a SINGLE open 'feeder_connection' alert when the feeder
        device (ultrasonic telemetry) is offline or stale. When the device is
        fresh again, refresh the open alert's message (user acknowledges via
        Mark as Read). Returns list of newly created Alert objects for WS
        broadcast.
        """
        from .models import FeederTelemetry

        created = []
        param = 'feeder_connection'
        now = timezone.now()
        latest = FeederTelemetry.objects.order_by('-timestamp').first()

        age_sec = None
        if latest is not None and latest.timestamp is not None:
            age_sec = (now - latest.timestamp).total_seconds()

        stale = latest is None or (
            age_sec is not None and age_sec >= AlertService.FEEDER_STALE_SECONDS
        )

        if not stale:
            # Device online again → allow future alerts and refresh any open one.
            AlertService.clear_snooze(param)
            open_alert = Alert.objects.filter(parameter=param, resolved=False).first()
            if open_alert:
                recovered = (
                    'Feeder device / ultrasonic reconnected. '
                    'Please acknowledge this alert.'
                )
                if open_alert.message != recovered:
                    open_alert.message = recovered
                    open_alert.save(update_fields=['message'])
            return created

        if AlertService.is_snoozed(param):
            return created

        if latest is None:
            msg = 'Feeder device offline — ultrasonic disconnected (no telemetry yet).'
        else:
            when_str = timezone.localtime(latest.timestamp).strftime('%Y-%m-%d %H:%M:%S')
            msg = (
                f'Feeder device offline — ultrasonic disconnected. '
                f'Last telemetry at {when_str} ({age_sec:.0f}s ago).'
            )

        # Keep a single open alert; just refresh its timestamp/message.
        open_alert = Alert.objects.filter(parameter=param, resolved=False).first()
        if open_alert:
            if open_alert.message != msg:
                open_alert.message = msg
            open_alert.timestamp = now
            open_alert.save(update_fields=['message', 'timestamp'])
            return created

        lock_key = f'{AlertService._CREATE_LOCK_PREFIX}{param}'
        if not cache.add(lock_key, True, timeout=15):
            return created
        alert = None
        try:
            if Alert.objects.filter(parameter=param, resolved=False).exists():
                return created
            alert = Alert.objects.create(
                parameter=param,
                severity='critical',
                value=None,
                threshold_min=0,
                threshold_max=0,
                message=msg,
            )
        finally:
            cache.delete(lock_key)

        if alert is None:
            return created

        AlertService.notify_alert_async(alert)
        created.append(alert)
        logger.warning('[FEEDER] %s', msg)
        return created

    @staticmethod
    def check_feeder_level():
        """
        When ultrasonic distance is 32 cm or more, the hopper is low.
        One open 'feeder_level' alert; emails Settings → notification email
        on first create. Fresh telemetry only (ignore stale/offline readings).
        """
        from .models import Feeder, FeederTelemetry

        created = []
        param = 'feeder_level'
        threshold = AlertService.FEEDER_LOW_DISTANCE_CM
        now = timezone.now()

        feeder = Feeder.objects.first()
        if feeder is not None and getattr(feeder, 'alerts_enabled', True) is False:
            return created

        latest = FeederTelemetry.objects.order_by('-timestamp').first()
        if latest is None or latest.timestamp is None:
            return created

        age_sec = (now - latest.timestamp).total_seconds()
        if age_sec >= AlertService.FEEDER_STALE_SECONDS:
            return created

        dist = latest.distance_cm
        if dist is None:
            return created

        try:
            dist = float(dist)
        except (TypeError, ValueError):
            return created

        is_low = dist >= threshold

        if not is_low:
            AlertService.clear_snooze(param)
            open_alert = Alert.objects.filter(parameter=param, resolved=False).first()
            if open_alert:
                recovered = (
                    f'Feeder feed level recovered (ultrasonic {dist:.1f} cm, '
                    f'low at {threshold:.0f} cm or above). '
                    f'Please acknowledge this alert.'
                )
                if open_alert.message != recovered:
                    open_alert.message = recovered
                    open_alert.value = dist
                    open_alert.save(update_fields=['message', 'value'])
            return created

        if AlertService.is_snoozed(param):
            return created

        msg = (
            f'Feeder is low on feeds — please refill. '
            f'Ultrasonic distance {dist:.1f} cm '
            f'(low when {threshold:.0f} cm or above).'
        )

        open_alert = Alert.objects.filter(parameter=param, resolved=False).first()
        if open_alert:
            open_alert.message = msg
            open_alert.value = dist
            open_alert.timestamp = now
            open_alert.save(update_fields=['message', 'value', 'timestamp'])
            return created

        lock_key = f'{AlertService._CREATE_LOCK_PREFIX}{param}'
        if not cache.add(lock_key, True, timeout=15):
            return created
        alert = None
        try:
            if Alert.objects.filter(parameter=param, resolved=False).exists():
                return created
            alert = Alert.objects.create(
                parameter=param,
                severity='warning',
                value=dist,
                threshold_min=0,
                threshold_max=threshold,
                message=msg,
            )
        finally:
            cache.delete(lock_key)

        if alert is None:
            return created

        AlertService.notify_alert_async(alert)
        created.append(alert)
        logger.warning('[FEEDER_LEVEL] %s', msg)
        return created

    @staticmethod
    def check_disconnected_sensors(sensor_reading, dedupe_minutes=None):
        """
        Create critical alerts (+ email) when a sensor value is NULL.
        Also alert if the latest reading itself is stale (no data for 30s).
        Returns list of newly created Alert objects.
        """
        created = []
        now = timezone.now()
        dedupe_minutes = dedupe_minutes or AlertService.DISCONNECT_DEDUPE_MINUTES

        if sensor_reading is None:
            alert = AlertService._create_offline_alert(
                'Sensor stream offline — no readings in the database. '
                'Check WeMos WiFi and HTTP upload.'
            )
            if alert:
                created.append(alert)
            return created

        reading_time = sensor_reading.timestamp or now
        when_str = timezone.localtime(reading_time).strftime('%Y-%m-%d %H:%M:%S')
        age_sec = (now - reading_time).total_seconds()

        # Stale stream: no fresh reading for 30s → one offline alert
        if age_sec >= AlertService.STALE_READING_SECONDS:
            alert = AlertService._create_offline_alert(
                f'Sensor stream offline / stale. Last reading at {when_str} '
                f'({age_sec:.0f}s ago). Check WeMos WiFi and HTTP upload.'
            )
            if alert:
                created.append(alert)
            return created

        # Fresh stream again → allow future offline alerts, but do NOT auto-resolve
        # open offline alerts. "Mark as Read" is the only way to clear them (UI maps
        # resolved → read). Auto-resolve made alerts look "already read" without the user.
        AlertService.clear_snooze('sensor_offline')
        open_offline = Alert.objects.filter(
            parameter='sensor_offline', severity='critical', resolved=False,
        ).first()
        if open_offline:
            recovered_msg = (
                f'Sensor stream recovered at {when_str} (was offline). '
                f'Please acknowledge this alert.'
            )
            if open_offline.message != recovered_msg:
                open_offline.message = recovered_msg
                open_offline.save(update_fields=['message'])

        for param in AlertService.SENSOR_PARAMS:
            value = getattr(sensor_reading, param, None)
            # Only NULL = disconnected. Numeric 0 is a valid reading.
            if value is not None:
                # Sensor back online → allow future disconnect alerts; leave open ones
                # for the user to acknowledge (do not auto-mark as read).
                AlertService.clear_snooze(param)
                open_disc = Alert.objects.filter(
                    parameter=param,
                    severity='critical',
                    resolved=False,
                    value__isnull=True,
                ).first()
                if open_disc:
                    label = AlertService._param_label(param)
                    recovered = (
                        f'{label} sensor reading restored at {when_str}. '
                        f'Please acknowledge this alert.'
                    )
                    if open_disc.message != recovered:
                        open_disc.message = recovered
                        open_disc.save(update_fields=['message'])
                continue

            if AlertService.is_snoozed(param):
                continue

            # Any open unresolved disconnect alert for this param → keep one
            if Alert.objects.filter(
                parameter=param,
                severity='critical',
                resolved=False,
                value__isnull=True,
            ).exists():
                continue

            # Also block rapid recreate after mark-as-read (create-time window)
            cutoff = now - timedelta(minutes=dedupe_minutes)
            if Alert.objects.filter(
                parameter=param,
                severity='critical',
                value__isnull=True,
                timestamp__gte=cutoff,
            ).exists():
                continue

            lock_key = f'{AlertService._CREATE_LOCK_PREFIX}{param}'
            if not cache.add(lock_key, True, timeout=15):
                continue
            alert = None
            try:
                if Alert.objects.filter(
                    parameter=param, severity='critical', resolved=False, value__isnull=True,
                ).exists():
                    continue
                label = AlertService._param_label(param)
                msg = (
                    f'{label} sensor disconnected / no reading (NULL) at {when_str}. '
                    f'Check probe wiring and Arduino output for {param.upper()}.'
                )
                alert = Alert.objects.create(
                    parameter=param,
                    severity='critical',
                    value=None,
                    threshold_min=0,
                    threshold_max=0,
                    message=msg,
                )
            finally:
                cache.delete(lock_key)

            if alert is None:
                continue

            AlertService.notify_alert_async(alert)
            created.append(alert)
            logger.warning('[DISCONNECT] %s', msg)

        return created
