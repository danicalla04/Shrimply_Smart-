#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
django.setup()

from api.models import Threshold, SensorReading, Alert

# Check thresholds
print('=== THRESHOLDS ===')
thresholds = Threshold.objects.all().values()
if thresholds.exists():
    for t in thresholds:
        print(f"{t['parameter']}: {t['min_value']}-{t['max_value']} {t['unit']}")
else:
    print('No thresholds configured')

# Check latest sensor reading
print('\n=== LATEST SENSOR READING ===')
latest = SensorReading.objects.first()
if latest:
    print(f"Temperature: {latest.temperature}°C")
    print(f"pH: {latest.ph}")
    print(f"Turbidity: {latest.turbidity} NTU")
    print(f"TDS: {latest.tds} ppm")
    print(f"Timestamp: {latest.timestamp}")
else:
    print('No sensor readings found')

# Check recent alerts
print('\n=== RECENT ALERTS ===')
total_alerts = Alert.objects.count()
print(f'Total alerts in database: {total_alerts}')
if total_alerts > 0:
    alerts = Alert.objects.all()[:10]
    for a in alerts:
        print(f"  {a.timestamp} - {a.severity}: {a.parameter} = {a.value} (range: {a.threshold_min}-{a.threshold_max})")
else:
    print('No alerts found')

# Summary statistics
print('\n=== STATISTICS ===')
print(f'SensorReading count: {SensorReading.objects.count()}')
print(f'Alert count: {Alert.objects.count()}')
print(f'Threshold count: {Threshold.objects.count()}')
