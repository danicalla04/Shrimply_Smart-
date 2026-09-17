#!/usr/bin/env python
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
sys.path.insert(0, os.path.dirname(__file__))

import django

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from rest_framework_simplejwt.tokens import RefreshToken  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402


def main():
    user = User.objects.get(username='admin')
    token = str(RefreshToken.for_user(user).access_token)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    for url in ['/api/seasons/9/growth_metrics/', '/api/seasons/9/growth_predictions/']:
        print(f"\nGET {url}")
        resp = client.get(url)
        print('Status:', resp.status_code)
        try:
            print('JSON:', resp.json())
        except Exception:
            print('Body:', resp.content[:500])


if __name__ == '__main__':
    main()
