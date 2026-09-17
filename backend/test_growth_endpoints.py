#!/usr/bin/env python
"""Quick diagnostic for Season growth endpoints.

Usage:
    python test_growth_endpoints.py
    python test_growth_endpoints.py --username admin
    python test_growth_endpoints.py --season-id 9
"""

import argparse
import json
import os
import sys
import traceback

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.contrib.auth.models import User
from django.test import Client
from rest_framework_simplejwt.tokens import RefreshToken


def call(client: Client, url: str):
    print(f"\n=== GET {url} ===")
    try:
        resp = client.get(url)
    except Exception as exc:
        print("EXCEPTION:")
        traceback.print_exc()
        return

    print(f"Status: {resp.status_code}")
    ct = resp.get('Content-Type', '')
    print(f"Content-Type: {ct}")
    body_text = resp.content.decode('utf-8', errors='replace')
    if 'application/json' in ct:
        try:
            print(json.dumps(resp.json(), indent=2)[:4000])
        except Exception:
            print(body_text[:4000])
    else:
        print(body_text[:2000])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', default=None)
    parser.add_argument('--season-id', type=int, default=None)
    args = parser.parse_args()

    if args.username:
        user = User.objects.filter(username=args.username).first()
    else:
        user = User.objects.first()

    if not user:
        raise SystemExit('No matching user found')

    tokens = RefreshToken.for_user(user)
    access_token = str(tokens.access_token)

    client = Client()
    client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {access_token}'

    # Choose season
    from api.models import Season

    if args.season_id:
        season = Season.objects.filter(id=args.season_id, user=user).first()
    else:
        season = Season.objects.filter(user=user).order_by('-id').first()

    if not season:
        raise SystemExit('No matching season found for user')
    print(f"User: {user.username} (ID={user.id})")
    print(f"Season under test: ID={season.id} name={season.name}")

    call(client, f'/api/seasons/{season.id}/growth_metrics/')
    call(client, f'/api/seasons/{season.id}/growth_predictions/')
