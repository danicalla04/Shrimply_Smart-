#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
sys.path.insert(0, os.path.dirname(__file__))

django.setup()

from django.contrib.auth.models import User
from api.models import Season
from datetime import datetime


def _get_arg_value(flag: str):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


username = _get_arg_value('--username') or os.environ.get('SEASON_USERNAME') or 'admin'
name = _get_arg_value('--name') or os.environ.get('SEASON_NAME') or 'Test Shrimp Season'

user = User.objects.filter(username=username).first() or User.objects.first()
if not user:
    print('✗ No users found!')
    sys.exit(1)

s = Season.objects.create(
    name=name,
    user=user,
    is_active=True,
    start_date=datetime.now().date(),
    current_shrimp_quantity=50000,
    average_shrimp_weight_grams=2.5,
)
print(f'✓ Created season ID {s.id}: {s.name} for user {user.username} (id={user.id})')
