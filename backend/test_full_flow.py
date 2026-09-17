#!/usr/bin/env python
"""
Comprehensive test of the threshold save functionality
to match what the React frontend will do.
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

def test_threshold_save_flow():
    """Test the complete threshold save flow."""
    print("\n" + "="*60)
    print("THRESHOLD SAVE FUNCTIONALITY TEST")
    print("="*60 + "\n")
    
    # 1. Setup
    print("[1] SETUP: Creating test user and client")
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={'is_superuser': False, 'is_staff': False}
    )
    if created:
        user.set_password('testpass123')
        user.save()
        print("    ✓ Created test user")
    else:
        print("    ✓ Test user exists")
    
    client = Client()
    client.force_login(user)
    print("    ✓ User logged in")
    
    # 2. Reset thresholds to defaults
    print("\n[2] RESET: Setting thresholds to defaults")
    default_thresholds = {
        'temperature': {'min': 20, 'max': 35, 'unit': 'C'},
        'ph': {'min': 4.0, 'max': 10.0, 'unit': ''},
        'turbidity': {'min': 25, 'max': 50, 'unit': 'NTU'},
        'tds': {'min': 100, 'max': 160, 'unit': 'ppm'},
    }
    
    reset_response = client.post(
        '/api/thresholds/update_all/',
        data=json.dumps(default_thresholds),
        content_type='application/json'
    )
    print(f"    ✓ Reset response: {reset_response.status_code}")
    print(f"    Reset data: {json.dumps(reset_response.json(), indent=6)}")
    
    # 3. Fetch thresholds (like frontend does on page load)
    print("\n[3] FETCH: Get thresholds from server")
    fetch_response = client.get('/api/thresholds/all/')
    print(f"    ✓ Fetch status: {fetch_response.status_code}")
    fetched_data = fetch_response.json()
    print(f"    Fetched data: {json.dumps(fetched_data, indent=6)}")
    
    # 4. Simulate user editing thresholds in UI
    print("\n[4] EDIT: User modifies threshold ranges")
    modified_thresholds = {
        'temperature': {'min': 25, 'max': 32, 'unit': 'C'},  # Changed
        'ph': {'min': 6.5, 'max': 8.5, 'unit': ''},  # Changed
        'turbidity': {'min': 1.0, 'max': 3.0, 'unit': 'NTU'},  # Changed
        'tds': {'min': 120, 'max': 200, 'unit': 'ppm'},  # Changed
    }
    print(f"    Original temperature: 20-35 -> Modified: 25-32")
    print(f"    Original pH: 4.0-10.0 -> Modified: 6.5-8.5")
    print(f"    Original turbidity: 25-50 -> Modified: 1.0-3.0")
    print(f"    Original TDS: 100-160 -> Modified: 120-200")
    
    # 5. Save (CRITICAL: exactly like frontend does)
    print("\n[5] SAVE: Send modified thresholds to server")
    print(f"    Sending JSON: {json.dumps(modified_thresholds, indent=6)}")
    save_response = client.post(
        '/api/thresholds/update_all/',
        data=json.dumps(modified_thresholds),
        content_type='application/json'
    )
    print(f"    ✓ Save response status: {save_response.status_code}")
    if save_response.status_code != 200:
        print(f"    ✗ ERROR: Expected 200, got {save_response.status_code}")
        print(f"    Response: {save_response.json()}")
        return False
    
    save_data = save_response.json()
    print(f"    Response data: {json.dumps(save_data, indent=6)}")
    
    # 6. Verify database was updated
    print("\n[6] VERIFY: Check database contains updated values")
    success = True
    for param, expected_values in modified_thresholds.items():
        threshold = Threshold.objects.get(parameter=param)
        if (threshold.min_value == expected_values['min'] and
            threshold.max_value == expected_values['max']):
            print(f"    ✓ {param}: {threshold.min_value}-{threshold.max_value} (CORRECT)")
        else:
            print(f"    ✗ {param}: {threshold.min_value}-{threshold.max_value} (EXPECTED {expected_values['min']}-{expected_values['max']})")
            success = False
    
    # 7. Refetch to simulate page reload
    print("\n[7] REFETCH: Simulate user navigating away and back")
    refetch_response = client.get('/api/thresholds/all/')
    refetch_data = refetch_response.json()
    print(f"    Refetched data: {json.dumps(refetch_data, indent=6)}")
    
    print("\n" + "="*60)
    if success and save_response.status_code == 200:
        print("✓ ALL TESTS PASSED - Threshold save is working correctly!")
        print("="*60 + "\n")
        return True
    else:
        print("✗ TESTS FAILED - Threshold save has issues")
        print("="*60 + "\n")
        return False

if __name__ == '__main__':
    success = test_threshold_save_flow()
    sys.exit(0 if success else 1)
