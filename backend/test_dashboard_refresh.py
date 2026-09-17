#!/usr/bin/env python
"""
Test threshold save with actual Dashboard refresh simulation
"""
import os
import sys
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from api.models import Threshold

def test_dashboard_threshold_refresh():
    """Simulate Dashboard -> Settings -> Dashboard flow"""
    print("\n" + "="*70)
    print("DASHBOARD THRESHOLD REFRESH TEST")
    print("="*70 + "\n")
    
    # Setup
    user, _ = User.objects.get_or_create(username='dashtest', defaults={'is_superuser': False})
    if not user.has_usable_password():
        user.set_password('testpass')
        user.save()
    
    client = Client()
    client.force_login(user)
    
    # 1. Dashboard initial load - fetch thresholds
    print("[1] DASHBOARD INITIAL LOAD: GET /api/thresholds/all/")
    resp1 = client.get('/api/thresholds/all/')
    data1 = resp1.json()
    print(f"    Status: {resp1.status_code}")
    print(f"    Response: {json.dumps(data1, indent=4)}")
    initial_temp_min = data1.get('temperature', {}).get('min')
    print(f"    Temperature Min Saved in Response: {initial_temp_min}")
    
    # 2. User goes to Settings and modifies thresholds
    print("\n[2] USER EDITS SETTINGS: POST /api/thresholds/update_all/")
    new_thresholds = {
        'temperature': {'min': 22, 'max': 28, 'unit': 'C'},
        'ph': {'min': 6.0, 'max': 8.0, 'unit': ''},
        'turbidity': {'min': 2.0, 'max': 4.0, 'unit': 'NTU'},
        'tds': {'min': 150, 'max': 200, 'unit': 'ppm'},
    }
    resp2 = client.post(
        '/api/thresholds/update_all/',
        data=json.dumps(new_thresholds),
        content_type='application/json'
    )
    data2 = resp2.json()
    print(f"    Status: {resp2.status_code}")
    print(f"    Saved Response: {json.dumps(data2, indent=4)}")
    
    # 3. User returns to Dashboard - should fetch fresh thresholds
    print("\n[3] DASHBOARD REFRESH: GET /api/thresholds/all/ (after focus)")
    resp3 = client.get('/api/thresholds/all/')
    data3 = resp3.json()
    print(f"    Status: {resp3.status_code}")
    print(f"    Response: {json.dumps(data3, indent=4)}")
    
    # Verify
    print("\n[4] VERIFICATION:")
    success = True
    
    # Check initial load has data
    if data1.get('temperature') is None:
        print(f"    ✗ Initial load: temperature not in response")
        success = False
    else:
        print(f"    ✓ Initial load returned valid thresholds")
    
    # Check save worked
    if data2.get('temperature', {}).get('min') != 22:
        print(f"    ✗ Save failed: temperature min is {data2.get('temperature', {}).get('min')}, expected 22")
        success = False
    else:
        print(f"    ✓ Save successful: temperature range updated to 22-28")
    
    # Check refresh returns updated values
    if data3.get('temperature', {}).get('min') != 22:
        print(f"    ✗ Refresh failed: temperature min is {data3.get('temperature', {}).get('min')}, expected 22")
        success = False
    else:
        print(f"    ✓ Refresh successful: Dashboard sees updated thresholds")
    
    # Check database
    print("\n[5] DATABASE CHECK:")
    temp_threshold = Threshold.objects.get(parameter='temperature')
    print(f"    temperature: {temp_threshold.min_value}-{temp_threshold.max_value} {temp_threshold.unit}")
    if temp_threshold.min_value == 22:
        print(f"    ✓ Database persisted correctly")
    else:
        print(f"    ✗ Database not updated")
        success = False
    
    print("\n" + "="*70)
    if success:
        print("✓ ALL TESTS PASSED - Threshold save and refresh working!")
    else:
        print("✗ SOME TESTS FAILED - Check output above")
    print("="*70 + "\n")
    
    return success

if __name__ == '__main__':
    success = test_dashboard_threshold_refresh()
    sys.exit(0 if success else 1)
