#!/usr/bin/env python
"""
Update water quality thresholds in the database to optimal shrimp farming ranges
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
sys.path.insert(0, os.path.dirname(__file__))

django.setup()

from api.models import Threshold

# Shrimp farming optimal ranges
OPTIMAL_THRESHOLDS = {
    'temperature': {'min': 20, 'max': 35, 'unit': '°C'},
    'ph': {'min': 3.0, 'max': 8.0, 'unit': ''},
    'turbidity': {'min': 25, 'max': 50, 'unit': 'NTU'},
    'tds': {'min': 100, 'max': 160, 'unit': 'ppm'},
}

print("=" * 70)
print("UPDATING SENSOR THRESHOLDS TO OPTIMAL SHRIMP FARMING RANGES")
print("=" * 70)

for param, values in OPTIMAL_THRESHOLDS.items():
    threshold, created = Threshold.objects.update_or_create(
        parameter=param,
        defaults={
            'min_value': values['min'],
            'max_value': values['max'],
            'unit': values['unit']
        }
    )
    
    action = "✅ Created" if created else "✅ Updated"
    print(f"{action} {param}: {threshold.min_value} - {threshold.max_value} {threshold.unit}")

print("\n" + "=" * 70)
print("✅ ALL THRESHOLDS UPDATED SUCCESSFULLY")
print("=" * 70)

# Display all current thresholds
print("\nCurrent thresholds in database:")
print("-" * 70)
for threshold in Threshold.objects.all().order_by('parameter'):
    print(f"  {threshold.parameter.upper():12} : {threshold.min_value:7.1f} - {threshold.max_value:7.1f} {threshold.unit}")
print("-" * 70)
