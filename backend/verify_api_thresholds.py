#!/usr/bin/env python
"""
Verify API endpoint returns correct thresholds
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
sys.path.insert(0, os.path.dirname(__file__))

django.setup()

from django.test import RequestFactory
from api.views import ThresholdViewSet

# Create a test request
factory = RequestFactory()
request = factory.get('/api/thresholds/all/')

# Create a mock user
class MockUser:
    def is_authenticated(self):
        return True
    is_authenticated = property(lambda self: True)

request.user = MockUser()

# Get the viewset
viewset = ThresholdViewSet()
viewset.request = request
viewset.format_kwarg = None

# Call the 'all' action
response = viewset.all(request)

print("\n" + "=" * 70)
print("API Endpoint Response (/api/thresholds/all/)")
print("=" * 70)
print(f"Status Code: {response.status_code}")
print(f"Response Data: {response.data}")
print("=" * 70)

# Verify each threshold
print("\nVerification:")
print("-" * 70)

expected = {
    'temperature': {'min': 20, 'max': 35},
    'ph': {'min': 3.0, 'max': 8.0},
    'turbidity': {'min': 25, 'max': 50},
    'tds': {'min': 100, 'max': 160},
}

all_correct = True
for param, expected_vals in expected.items():
    if param in response.data:
        actual = response.data[param]
        is_correct = (actual['min'] == expected_vals['min'] and 
                      actual['max'] == expected_vals['max'])
        status = "✅" if is_correct else "❌"
        print(f"{status} {param.upper():12}: API returns {actual['min']} - {actual['max']}")
        if not is_correct:
            all_correct = False
    else:
        print(f"❌ {param.upper():12}: NOT IN API RESPONSE")
        all_correct = False

print("-" * 70)
if all_correct:
    print("✅ API ENDPOINT RETURNS CORRECT VALUES!")
else:
    print("❌ API ENDPOINT HAS INCORRECT VALUES")
print("=" * 70)
