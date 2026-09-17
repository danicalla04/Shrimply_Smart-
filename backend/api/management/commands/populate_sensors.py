from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from api.models import SensorReading
import random


class Command(BaseCommand):
    help = 'Populate database with sample sensor readings'

    def handle(self, *args, **kwargs):
        # Clear existing readings
        SensorReading.objects.all().delete()
        self.stdout.write(self.style.WARNING('Cleared existing sensor readings'))
        
        # Create 30 days of sensor readings
        now = timezone.now()
        readings = []
        
        for i in range(30):
            # Generate realistic values with some variation
            temperature = round(28.0 + random.uniform(-2, 3), 1)
            ph = round(7.2 + random.uniform(-0.5, 0.8), 1)
            oxygen = round(6.8 + random.uniform(-1.5, 2), 1)
            tds = int(300 + random.uniform(-50, 100))
            
            # Create reading with timestamp going back in time
            timestamp = now - timedelta(days=i, hours=random.randint(0, 23), minutes=random.randint(0, 59))
            
            reading = SensorReading.objects.create(
                temperature=temperature,
                ph=ph,
                oxygen=oxygen,
                tds=tds,
                timestamp=timestamp
            )
            readings.append(reading)
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {len(readings)} sensor readings')
        )
        
        # Show summary
        self.stdout.write('\nSummary:')
        self.stdout.write(f'Temperature range: {min(r.temperature for r in readings):.1f} - {max(r.temperature for r in readings):.1f} °C')
        self.stdout.write(f'pH range: {min(r.ph for r in readings):.1f} - {max(r.ph for r in readings):.1f}')
        self.stdout.write(f'Oxygen range: {min(r.oxygen for r in readings):.1f} - {max(r.oxygen for r in readings):.1f} mg/L')
        self.stdout.write(f'TDS range: {min(r.tds for r in readings)} - {max(r.tds for r in readings)} ppm')
