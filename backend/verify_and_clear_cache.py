#!/usr/bin/env python
"""
Clear frontend cache by logging all users out (which will force them to re-login and refresh data)
Or create a console message to clear localStorage
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
sys.path.insert(0, os.path.dirname(__file__))

django.setup()

print("\n" + "=" * 70)
print("FRONTEND CACHE CLEARING INSTRUCTIONS")
print("=" * 70)
print("\nThe database thresholds have been updated successfully!")
print("To clear the frontend cache and see the new values:\n")
print("Option 1 (Browser Dev Tools):")
print("  1. Open the ShrimplySmart web application")
print("  2. Press F12 to open Developer Tools")
print("  3. Go to Application > Local Storage")
print("  4. Find and delete 'sensorThresholds' key")
print("  5. Refresh the page (F5 or Ctrl+R)\n")
print("Option 2 (Automatic - Logout & Login):")
print("  1. Click Logout in the application")
print("  2. Log back in")
print("  3. The app will fetch fresh thresholds from the database\n")
print("=" * 70)
print("\nVerifying all database thresholds are correct:")
print("=" * 70)

from api.models import Threshold

expected = {
    'temperature': {'min': 20, 'max': 35},
    'ph': {'min': 3.0, 'max': 8.0},
    'turbidity': {'min': 25, 'max': 50},
    'tds': {'min': 100, 'max': 160},
}

all_correct = True
for param, expected_vals in expected.items():
    try:
        threshold = Threshold.objects.get(parameter=param)
        is_correct = (threshold.min_value == expected_vals['min'] and 
                      threshold.max_value == expected_vals['max'])
        status = "✅" if is_correct else "❌"
        print(f"{status} {param.upper():12} : {threshold.min_value:7.1f} - {threshold.max_value:7.1f}")
        if not is_correct:
            all_correct = False
    except Threshold.DoesNotExist:
        print(f"❌ {param.upper():12} : NOT FOUND IN DATABASE")
        all_correct = False

print("=" * 70)
if all_correct:
    print("✅ ALL THRESHOLDS ARE CORRECT IN DATABASE!")
else:
    print("❌ Some thresholds are incorrect. Please review above.")
print("=" * 70)
