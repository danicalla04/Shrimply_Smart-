#!/usr/bin/env python
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()
from api.models import Season
from django.contrib.auth.models import User

user = User.objects.first()
print(f"\nUser: {user.username} (ID={user.id})")

seasons = Season.objects.all()
print(f"\nTotal seasons in database: {seasons.count()}")
for s in seasons:
    print(f"  - ID {s.id}: {s.name} (user_id={s.user_id}, is_active={s.is_active})")

user_seasons = Season.objects.filter(user=user)
print(f"\nSeasons for user {user.username}: {user_seasons.count()}")
for s in user_seasons:
    print(f"  - ID {s.id}: {s.name} (is_active={s.is_active})")
