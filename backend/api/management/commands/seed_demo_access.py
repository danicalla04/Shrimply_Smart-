"""Provision the requested accounts without creating activity history."""

import secrets
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.permissions import set_user_privileges


MANILA = ZoneInfo('Asia/Manila')
JOINED_ON = date(2026, 10, 16)
PEOPLE = (
    ('ray.goco', 'Ray', 'Goco', True),
    ('leizl.reyes.abas', 'Leizl', 'Reyes Abas', False),
    ('mark.royan', 'Mark', 'Royan', False),
    ('darwin.baculo', 'Darwin', 'Baculo', False),
    ('felix.flores', 'Felix', 'Flores', False),
)


class Command(BaseCommand):
    help = 'Create the five requested accounts with October 16, 2026 join dates.'

    def add_arguments(self, parser):
        parser.add_argument('--reset-passwords', action='store_true', help='Generate and print new passwords for existing requested accounts.')

    def handle(self, *args, **options):
        new_credentials = []
        existing_accounts = []
        with transaction.atomic():
            for username, first_name, last_name, is_admin in PEOPLE:
                user = User.objects.filter(username__iexact=username).first()
                if user and (user.first_name, user.last_name) != (first_name, last_name):
                    raise CommandError(f'Username {username} belongs to another person; no changes were saved.')
                if user is None:
                    password = secrets.token_urlsafe(18)
                    user = User.objects.create_user(
                        username=username, password=password, first_name=first_name,
                        last_name=last_name, is_staff=is_admin, is_superuser=False,
                        is_active=True,
                    )
                    User.objects.filter(pk=user.pk).update(
                        date_joined=datetime.combine(JOINED_ON, time(9), tzinfo=MANILA),
                    )
                    new_credentials.append((username, password))
                else:
                    user.is_staff = is_admin
                    user.is_superuser = False
                    user.is_active = True
                    update_fields = ['is_staff', 'is_superuser', 'is_active']
                    if options['reset_passwords']:
                        password = secrets.token_urlsafe(18)
                        user.set_password(password)
                        update_fields.append('password')
                        new_credentials.append((username, password))
                    else:
                        existing_accounts.append(username)
                    user.save(update_fields=update_fields)
                set_user_privileges(user, {'create': False, 'update': False, 'delete': False})

        for username, password in new_credentials:
            self.stdout.write(f'CREDENTIALS  username={username}  temporary_password={password}')
        for username in existing_accounts:
            self.stdout.write(f'EXISTING ACCOUNT  username={username}  password unchanged; join date unchanged')
        self.stdout.write(self.style.SUCCESS(
            f'Accounts ready: {len(PEOPLE)}. '
            'Copy new passwords now; they are not stored in plain text.'
        ))
