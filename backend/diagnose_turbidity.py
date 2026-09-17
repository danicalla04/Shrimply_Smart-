#!/usr/bin/env python
"""
Analyze turbidity sensor readings and help diagnose the issue
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
django.setup()

from api.models import SensorReading
from datetime import timedelta
from django.utils import timezone

print("\n" + "="*70)
print("TURBIDITY SENSOR DIAGNOSTIC")
print("="*70 + "\n")

# Get recent readings
recent = SensorReading.objects.all()[:20]

print("[1] RECENT SENSOR READINGS (last 20)")
print(f"    {'Temperature':>12} {'pH':>8} {'TDS':>8} {'Turbidity':>12}")
print("    " + "-"*45)

turbidity_readings = []
for reading in recent:
    print(f"    {reading.temperature:>12.1f}°C {reading.ph:>8.2f} {reading.tds:>8.0f} {reading.turbidity:>12.2f} NTU")
    if reading.turbidity is not None:
        turbidity_readings.append(reading.turbidity)

# Analysis
print("\n[2] TURBIDITY ANALYSIS")
if turbidity_readings:
    avg_turb = sum(turbidity_readings) / len(turbidity_readings)
    max_turb = max(turbidity_readings)
    min_turb = min(turbidity_readings)
    
    print(f"    Min: {min_turb:.2f} NTU")
    print(f"    Max: {max_turb:.2f} NTU")
    print(f"    Avg: {avg_turb:.2f} NTU")
    
    print("\n[3] INTERPRETATION")
    if avg_turb > 2000:
        print("    ⚠️  CRITICAL: Turbidity is EXTREMELY high (>2000 NTU)")
        print("    This indicates either:")
        print("    • Sensor is miscalibrated or broken")
        print("    • Water is completely opaque (pure mud)")
        print("    • Sensor is not connected or on wrong MUX channel")
    elif avg_turb > 500:
        print("    ⚠️  HIGH: Turbidity is very high (500-2000 NTU)")
        print("    This suggests sensor miscalibration or very turbid water")
    elif avg_turb > 100:
        print("    ⚠️  ELEVATED: Turbidity is elevated (100-500 NTU)")
        print("    Water needs cleaning or better filtration")
    elif avg_turb > 50:
        print("    ⚠️  MODERATE: Turbidity is above ideal (50-100 NTU)")
    else:
        print("    ✓ OK: Turbidity is within acceptable range (<50 NTU)")
    
    print("\n[4] RECOMMENDED NEXT STEPS")
    if avg_turb > 1000:
        print("    1. Check if turbidity sensor is actually connected")
        print("    2. Verify it's on MUX channel 2 (CH_TURB)")
        print("    3. Read Serial Monitor from Arduino to see raw voltage values")
        print("    4. Test with clear tap water to recalibrate sensor")
        print("    5. Consider if the 1.5x voltage divider multiplier is correct")
    else:
        print("    1. Check water clarity visually")
        print("    2. If water looks clear but readings are high, recalibrate sensor")
        print("    3. Test sensor against known turbidity standards")

print("\n" + "="*70)
print("END DIAGNOSTIC")
print("="*70 + "\n")
