#!/usr/bin/env python
import os
import sys
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from api.models import Threshold

print("\n=== Testing Threshold API ===\n")

# 1. Check current thresholds
print("[1] Current Thresholds:")
for t in Threshold.objects.all():
    print(f"    - {t.parameter}: {t.min_value}-{t.max_value} {t.unit}")

# 2. Create admin user if needed
user, created = User.objects.get_or_create(
    username='admin',
    defaults={'is_superuser': True, 'is_staff': True}
)
if created:
    user.set_password('admin123')
    user.save()
    print("\n[Created admin user]")

# 3. Test API with client
client = Client()
client.force_login(user)

# Test GET
print("\n[2] GET /api/thresholds/all/")
response = client.get('/api/thresholds/all/')
print(f"    Status: {response.status_code}")
print(f"    Data: {response.json()}")

# Test POST
print("\n[3] POST /api/thresholds/update_all/")
update_data = {
    'temperature': {'min': 25, 'max': 30, 'unit': 'C'},
    'ph': {'min': 7.0, 'max': 8.0, 'unit': ''},
    'turbidity': {'min': 1.0, 'max': 2.0, 'unit': 'NTU'},
    'tds': {'min': 150, 'max': 250, 'unit': 'ppm'},
}
response = client.post(
    '/api/thresholds/update_all/',
    data=json.dumps(update_data),
    content_type='application/json'
)
print(f"    Status: {response.status_code}")
print(f"    Data: {response.json()}")

# 4. Verify database
print("\n[4] Database After Update:")
for t in Threshold.objects.all():
    print(f"    - {t.parameter}: {t.min_value}-{t.max_value} {t.unit}")

print("\n=== Test Complete ===\n")
