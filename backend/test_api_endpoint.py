#!/usr/bin/env python
import os, sys, django, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from django.test import Client

# Get a valid token for the user
user = User.objects.first()
tokens = RefreshToken.for_user(user)
access_token = str(tokens.access_token)

print(f"User: {user.username} (ID={user.id})")
print(f"Access Token: {access_token[:20]}...")

# Make an API request to /api/seasons/
client = Client()
response = client.get(
    '/api/seasons/',
    HTTP_AUTHORIZATION=f'Bearer {access_token}'
)

print(f"\nAPI Response Status: {response.status_code}")
print(f"API Response Content-Type: {response.get('Content-Type')}")
print(f"\nAPI Response Body:")
print(json.dumps(response.json(), indent=2))
