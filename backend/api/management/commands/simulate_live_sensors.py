"""Insert dummy live sensor + ultrasonic packets every 5 seconds."""

import math
import random
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import FeederTelemetry, SensorReading


class Command(BaseCommand):
    help = 'Insert dummy water-quality and ultrasonic readings every 5 seconds (Ctrl+C to stop)'

    def add_arguments(self, parser):
        parser.add_argument('--interval', type=float, default=5, help='Seconds between inserts (default 5)')
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
        tick = 0
        self.stdout.write(self.style.SUCCESS(
            f'Simulating live WeMos packets every {interval:.0f}s. Ultrasonic 20-37 cm. Ctrl+C to stop.'
        ))
        try:
            while True:
                now = timezone.now()
                wave = (math.sin(tick / 8.0) + 1) / 2  # 0..1
                temperature = round(27.4 + 1.6 * math.sin(tick / 6.0) + random.uniform(-0.15, 0.15), 1)
                ph = round(7.35 + 0.25 * math.sin(tick / 9.0) + random.uniform(-0.04, 0.04), 2)
                turbidity = round(6.5 + 3.5 * math.sin(tick / 7.0 + 1) + random.uniform(-0.3, 0.3), 1)
                tds = int(round(240 + 40 * math.sin(tick / 10.0) + random.uniform(-8, 8)))
                distance = round(20 + 17 * wave + random.uniform(-0.2, 0.2), 1)
                distance = max(20.0, min(37.0, distance))

                reading = SensorReading.objects.create(
                    temperature=temperature,
                    ph=ph,
                    turbidity=max(0.1, turbidity),
                    tds=max(50, tds),
                )
                FeederTelemetry.objects.create(
                    motor_state='OFF',
                    distance_cm=distance,
                    device_id='dummy-wemos',
                )
                hopper_pct = int(round(100 + ((distance - 20) * (10 - 100)) / 17))
                hopper_pct = max(0, min(100, hopper_pct))
                self.stdout.write(
                    f'[{now.strftime("%H:%M:%S")}] T={reading.temperature}C  pH={reading.ph}  '
                    f'NTU={reading.turbidity}  TDS={reading.tds}  ultrasonic={distance}cm (~{hopper_pct}%)'
                )
                if once:
                    return
                tick += 1
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nStopped dummy live feed.'))
