"""
Management command to check if thresholds are set up in the database
"""
from django.core.management.base import BaseCommand
from api.models import Threshold, SensorReading
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Check threshold and sensor data status in database'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== THRESHOLD STATUS ===\n'))
        
        thresholds = Threshold.objects.all()
        if not thresholds.exists():
            self.stdout.write(self.style.WARNING('❌ NO THRESHOLDS FOUND IN DATABASE'))
            self.stdout.write('Please create thresholds via the Settings page or run: check_thresholds --create\n')
        else:
            self.stdout.write(self.style.SUCCESS(f'✅ Found {thresholds.count()} thresholds:'))
            for t in thresholds:
                self.stdout.write(f'   {t.parameter}: {t.min_value} - {t.max_value} {t.unit}')
        
        self.stdout.write(self.style.SUCCESS('\n=== SENSOR DATA STATUS ===\n'))
        
        latest_reading = SensorReading.objects.first()
        if not latest_reading:
            self.stdout.write(self.style.WARNING('❌ NO SENSOR READINGS FOUND IN DATABASE'))
            self.stdout.write('Sensor data is not being saved. Check serial listener or Arduino connection.\n')
        else:
            age = timezone.now() - latest_reading.timestamp
            self.stdout.write(self.style.SUCCESS(f'✅ Latest sensor reading:'))
            self.stdout.write(f'   Temperature: {latest_reading.temperature}°C')
            self.stdout.write(f'   pH: {latest_reading.ph}')
            self.stdout.write(f'   Turbidity: {latest_reading.turbidity} NTU')
            self.stdout.write(f'   TDS: {latest_reading.tds} ppm')
            self.stdout.write(f'   Recorded: {latest_reading.timestamp} ({age.total_seconds():.0f}s ago)\n')
            
            count = SensorReading.objects.count()
            last_24h = SensorReading.objects.filter(
                timestamp__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            self.stdout.write(f'   Total readings: {count}')
            self.stdout.write(f'   Readings in last 24h: {last_24h}\n')
        
        self.stdout.write(self.style.SUCCESS('=== END CHECK ===\n'))
