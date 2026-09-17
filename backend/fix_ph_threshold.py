#!/usr/bin/env python
"""
Fix pH thresholds to correct values
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
sys.path.insert(0, os.path.dirname(__file__))

django.setup()

from api.models import Threshold

# Fix pH threshold
print("Fixing pH threshold...")
ph_threshold = Threshold.objects.get(parameter='ph')
ph_threshold.min_value = 3.0
ph_threshold.max_value = 8.0
ph_threshold.save()

print("\n" + "=" * 70)
print("Current thresholds in database:")
print("=" * 70)
for threshold in Threshold.objects.all().order_by('parameter'):
    print(f"  {threshold.parameter.upper():12} : {threshold.min_value:7.1f} - {threshold.max_value:7.1f} {threshold.unit}")
print("=" * 70)
