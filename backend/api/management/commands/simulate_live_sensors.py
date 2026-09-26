"""Update one live reading every 5 seconds. Insert a history row every 10 minutes."""

import random
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import FeederTelemetry, SensorReading

# 20 cm = 100% full, 32 cm = 10%
HOPPER_FULL_CM = 20.0
HOPPER_TEN_PERCENT_CM = 32.0
ULTRASONIC_EVERY_SEC = 300
INSERT_EVERY_SEC = 600


def _step(value, step, low, high):
    nxt = value + random.choice((-step, step))
    return round(max(low, min(high, nxt)), 2 if step < 1 else 1)


def _hopper_percent(distance):
    span = HOPPER_TEN_PERCENT_CM - HOPPER_FULL_CM
    pct = 100 + ((distance - HOPPER_FULL_CM) * (10 - 100)) / span
    return max(0, min(100, int(round(pct))))


class Command(BaseCommand):
    help = 'Update one live reading every 5 seconds and insert a history row every 10 minutes'

    def add_arguments(self, parser):
        parser.add_argument('--interval', type=float, default=5, help='Seconds between water-sensor inserts (default 5)')
        parser.add_argument('--once', action='store_true', help='Insert one packet and exit')
        parser.add_argument('--force', action='store_true', help='Override: insert simulated packets (disabled by default)')

    def handle(self, *args, **options):
        if not options.get('force'):
            self.stdout.write(self.style.WARNING(
                'Dummy live feed is disabled. Only real WeMos sensor packets are written to the database.\n'
                'Pass --force if you really need simulated packets again.'
            ))
            return

        interval = max(1.0, float(options['interval']))
        once = options['once']
        temperature = 28.0
        ph = 7.40
        turbidity = 8.0
        tds = 240
        distance = 24.0
        started = time.monotonic()
        last_ultrasonic = started
        last_insert = started

        reading = SensorReading.objects.create(
            temperature=temperature,
            ph=ph,
            turbidity=turbidity,
            tds=tds,
        )
        telemetry = FeederTelemetry.objects.create(
            motor_state='OFF',
            distance_cm=distance,
            device_id='dummy-wemos',
        )

        self.stdout.write(self.style.SUCCESS(
            f'One live reading updates every {interval:.0f}s. '
            f'A new database row is inserted every {INSERT_EVERY_SEC // 60} min. '
            f'Ultrasonic value changes every {ULTRASONIC_EVERY_SEC // 60} min. '
            f'20 cm = 100%, 32 cm = 10%. Ctrl+C to stop.'
        ))
        try:
            while True:
                now = timezone.now()
                temperature = _step(temperature, 0.1, 26.0, 30.0)
                ph = _step(ph, 0.01, 6.8, 8.2)
                turbidity = _step(turbidity, 0.1, 2.0, 20.0)
                tds = int(_step(tds, 1, 150, 320))

                if time.monotonic() - last_ultrasonic >= ULTRASONIC_EVERY_SEC:
                    distance = _step(distance, 0.5, HOPPER_FULL_CM, 36.0)
                    last_ultrasonic = time.monotonic()

                reading.temperature = round(temperature, 1)
                reading.ph = round(ph, 2)
                reading.turbidity = round(turbidity, 1)
                reading.tds = tds
                reading.timestamp = now
                reading.save(update_fields=['temperature', 'ph', 'turbidity', 'tds', 'timestamp'])

                telemetry.distance_cm = round(distance, 1)
                telemetry.timestamp = now
                telemetry.save(update_fields=['distance_cm', 'timestamp'])

                inserted = False
                if time.monotonic() - last_insert >= INSERT_EVERY_SEC:
                    SensorReading.objects.create(
                        temperature=reading.temperature,
                        ph=reading.ph,
                        turbidity=reading.turbidity,
                        tds=reading.tds,
                    )
                    FeederTelemetry.objects.create(
                        motor_state='OFF',
                        distance_cm=telemetry.distance_cm,
                        device_id='dummy-wemos',
                    )
                    # Keep the live row newest so the dashboard follows the 5-second changes.
                    reading.timestamp = timezone.now()
                    telemetry.timestamp = reading.timestamp
                    reading.save(update_fields=['timestamp'])
                    telemetry.save(update_fields=['timestamp'])
                    last_insert = time.monotonic()
                    inserted = True

                action = 'INSERTED' if inserted else 'updated'
                self.stdout.write(
                    f'[{now.strftime("%H:%M:%S")}] {action}  T={reading.temperature}C  pH={reading.ph}  '
                    f'NTU={reading.turbidity}  TDS={reading.tds}  '
                    f'ultrasonic={distance:.1f}cm (~{_hopper_percent(distance)}%)'
                )
                if once:
                    return
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nStopped dummy live feed.'))
