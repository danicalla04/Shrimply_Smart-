import logging
from dataclasses import dataclass
from typing import Optional

import requests
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class ServoScheduleTick:
    started_job_id: Optional[int] = None
    stopped_job_id: Optional[int] = None
    error: Optional[str] = None


def enqueue_servo_job(
    *,
    target_grams: int,
    on_at=None,
    device_id: str = "wemos-poller",
    calibration_grams_30s: float = 570.0,
) -> Optional[int]:
    """Insert a scheduled servo job into api_feedertelemetry.

    This assumes the table has been ALTERed to include:
      on_at, target_grams, calibration_grams_30s, schedule_status
    """
    if on_at is None:
        on_at = timezone.now()

    try:
        grams_int = int(target_grams)
    except Exception:
        logger.warning("Invalid target_grams=%r", target_grams)
        return None

    if grams_int <= 0:
        logger.warning("target_grams must be > 0")
        return None

    now = timezone.now()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO api_feedertelemetry
                    (timestamp, motor_state, distance_cm, device_id,
                     on_at, target_grams, calibration_grams_30s, schedule_status)
                VALUES
                    (%s, %s, %s, %s,
                     %s, %s, %s, %s)
                """,
                [
                    now,
                    "OFF",
                    None,
                    device_id,
                    on_at,
                    grams_int,
                    float(calibration_grams_30s),
                    "scheduled",
                ],
            )
            return int(cursor.lastrowid)
    except Exception as e:
        logger.warning("Failed to enqueue servo job: %s", e, exc_info=True)
        return None


def ensure_next_servo_job_seeded(*, device_id: str = "wemos-poller") -> Optional[int]:
    """Ensure there's a future scheduled servo job in api_feedertelemetry.

    Intended to run from a long-lived process (like the poller). This makes the
    schedule visible in MySQL (schedule_status='scheduled') and allows the
    servo to run automatically even if no browser page is open.

    Rules:
      - Only runs if Feeder.auto_enabled is True.
      - If a scheduled/running job already exists with on_at >= now, do nothing.
      - Otherwise compute (or refresh) Feeder.next_feed_at and insert one job.
    """
    # Lazy import to avoid circular imports at module load.
    from api.models import Feeder

    feeder = Feeder.objects.first()
    if not feeder:
        feeder = Feeder.objects.create()

    if not feeder.auto_enabled:
        return None

    now = timezone.now()

    # If we already have a future job queued, don't add another.
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM api_feedertelemetry
                WHERE schedule_status IN (%s, %s)
                  AND on_at IS NOT NULL
                  AND on_at >= %s
                  AND (device_id = %s OR device_id = '' OR device_id IS NULL)
                ORDER BY on_at ASC, id ASC
                LIMIT 1
                """,
                ["scheduled", "running", now, device_id],
            )
            if cursor.fetchone():
                return None
    except Exception as e:
        logger.warning("Failed checking existing servo jobs: %s", e, exc_info=True)

    # Refresh next_feed_at if missing or in the past.
    next_on_at = feeder.next_feed_at
    if not next_on_at or next_on_at <= now:
        next_on_at = feeder.get_next_feed_time()
        feeder.next_feed_at = next_on_at
        feeder.save(update_fields=["next_feed_at"])

    # Seed a scheduled job.
    return enqueue_servo_job(
        target_grams=int(getattr(feeder, "portion_grams", 50) or 50),
        on_at=next_on_at,
        device_id=device_id,
        calibration_grams_30s=570.0,
    )


def _get_base_url() -> str:
    return str(getattr(settings, "WEMOS_BASE_URL", "")).rstrip("/")


def _get_timeout_seconds(timeout: Optional[float]) -> float:
    if timeout is not None:
        return float(timeout)
    return float(getattr(settings, "WEMOS_PROXY_TIMEOUT_SEC", 2.0))


def _servo_on(*, base_url: str, timeout: float) -> None:
    resp = requests.get(f"{base_url}/api/servo/on", timeout=timeout)
    if not resp.ok:
        raise RuntimeError(f"servo_on HTTP {resp.status_code}: {resp.text[:200]}")


def _servo_off(*, base_url: str, timeout: float) -> None:
    resp = requests.get(f"{base_url}/api/servo/off", timeout=timeout)
    if not resp.ok:
        raise RuntimeError(f"servo_off HTTP {resp.status_code}: {resp.text[:200]}")


def process_servo_schedule_tick(
    *,
    device_id: str = "wemos-poller",
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> ServoScheduleTick:
    """Start/stop at most one scheduled job for this device.

    Logic:
      - If a job is running and off_at <= now -> call servo OFF and mark done.
      - If nothing is running and a job is scheduled and on_at <= now -> mark running and call servo ON.

    Uses raw SQL so it can work even if Django model doesn't include the extra columns.
    """
    tick = ServoScheduleTick()

    base = (base_url or _get_base_url()).rstrip("/")
    if not base:
        tick.error = "WEMOS_BASE_URL not configured"
        return tick

    t = _get_timeout_seconds(timeout)
    now = timezone.now()

    try:
        # 1) Stop due running job first.
        running_due_id = None
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM api_feedertelemetry
                WHERE schedule_status = %s
                  AND off_at IS NOT NULL
                  AND off_at <= %s
                  AND (device_id = %s OR device_id = '' OR device_id IS NULL)
                ORDER BY off_at ASC, id ASC
                LIMIT 1
                """,
                ["running", now, device_id],
            )
            row = cursor.fetchone()
            if row:
                running_due_id = int(row[0])

        if running_due_id is not None:
            try:
                _servo_off(base_url=base, timeout=t)
            except Exception as e:
                # Mark error so we don't hammer the device.
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE api_feedertelemetry
                        SET schedule_status=%s,
                            run_stopped_at=%s,
                            motor_state=%s,
                            stop_reason=%s
                        WHERE id=%s AND schedule_status=%s
                        """,
                        ["error", now, "OFF", "servo_off_failed", running_due_id, "running"],
                    )
                tick.error = f"Stop failed: {e}"
                return tick

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE api_feedertelemetry
                    SET schedule_status=%s,
                        run_stopped_at=%s,
                        motor_state=%s,
                        stop_reason=%s
                    WHERE id=%s AND schedule_status=%s
                    """,
                    ["done", now, "OFF", "grams_to_time", running_due_id, "running"],
                )
            tick.stopped_job_id = running_due_id
            return tick

        # 2) If any job is currently running (even if not due to stop), don't start another.
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM api_feedertelemetry
                WHERE schedule_status = %s
                  AND (device_id = %s OR device_id = '' OR device_id IS NULL)
                ORDER BY run_started_at DESC, id DESC
                LIMIT 1
                """,
                ["running", device_id],
            )
            if cursor.fetchone():
                return tick

        # 3) Start next due scheduled job.
        scheduled_id = None
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM api_feedertelemetry
                    WHERE schedule_status = %s
                      AND on_at IS NOT NULL
                      AND on_at <= %s
                      AND (device_id = %s OR device_id = '' OR device_id IS NULL)
                    ORDER BY on_at ASC, id ASC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    ["scheduled", now, device_id],
                )
                row = cursor.fetchone()
                if not row:
                    return tick

                scheduled_id = int(row[0])
                cursor.execute(
                    """
                    UPDATE api_feedertelemetry
                    SET schedule_status=%s,
                        run_started_at=%s,
                        motor_state=%s,
                        stop_reason=%s
                    WHERE id=%s AND schedule_status=%s
                    """,
                    ["running", now, "ON", "", scheduled_id, "scheduled"],
                )

        try:
            _servo_on(base_url=base, timeout=t)
        except Exception as e:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE api_feedertelemetry
                    SET schedule_status=%s,
                        run_stopped_at=%s,
                        motor_state=%s,
                        stop_reason=%s
                    WHERE id=%s AND schedule_status=%s
                    """,
                    ["error", now, "OFF", "servo_on_failed", scheduled_id, "running"],
                )
            tick.error = f"Start failed: {e}"
            return tick

        tick.started_job_id = scheduled_id
        return tick
    except Exception as e:
        tick.error = str(e)
        return tick
