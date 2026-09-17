#!/usr/bin/env python
"""Test the threshold API endpoint directly."""
import os
import sys
import django
import json

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from api.models import Threshold

def test_threshold_api():
    """Test threshold API endpoint."""
    print("\n=== Testing Threshold API ===\n")
    
    # 1. Check current thresholds in database
    print("[1] Current Thresholds in Database:")
    thresholds = Threshold.objects.all()
    print(f"    Count: {thresholds.count()}")
    for t in thresholds:
        print(f"    - {t.parameter}: {t.min_value}-{t.max_value} {t.unit}")
    
    # 2. Test GET /api/thresholds/all/
    print("\n[2] Testing GET /api/thresholds/all/")
    client = Client()
    user = User.objects.filter(username='admin').first()
    if not user:
        print("    ❌ Admin user not found. Run: python scripts/init_db.py")
        return False
    
    client.force_login(user)
    response = client.get('/api/thresholds/all/')
    print(f"    Status: {response.status_code}")
    print(f"    Response: {json.dumps(response.json(), indent=2)}")
    
    # 3. Test POST /api/thresholds/update_all/
    print("\n[3] Testing POST /api/thresholds/update_all/")
    update_data = {
        'temperature': {'min': 25, 'max': 30, 'unit': '°C'},
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
    print(f"    Response: {json.dumps(response.json(), indent=2)}")
    
    # 4. Verify database was updated
    print("\n[4] Verifying Database Update:")
    thresholds = Threshold.objects.all()
    for t in thresholds:
        print(f"    - {t.parameter}: {t.min_value}-{t.max_value} {t.unit}")
    
    print("\n=== Test Complete ===\n")
    return response.status_code == 200

if __name__ == '__main__':
    success = test_threshold_api()
    sys.exit(0 if success else 1)
