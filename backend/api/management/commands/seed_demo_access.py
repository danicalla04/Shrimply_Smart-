"""Provision the requested accounts and visibly simulated activity history."""

import secrets
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import ActivityLog
from api.permissions import set_user_privileges, user_privileges


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
    help = 'Create five named accounts and labeled demo activity from October 16, 2026.'

    def add_arguments(self, parser):
        parser.add_argument('--through', help='Last demo activity date (YYYY-MM-DD); defaults to today in Manila.')
        parser.add_argument('--reset-passwords', action='store_true', help='Generate and print new passwords for existing requested accounts.')

    def handle(self, *args, **options):
        today = datetime.now(MANILA).date()
        try:
            through = date.fromisoformat(options['through']) if options['through'] else today
        except ValueError as exc:
            raise CommandError('--through must be YYYY-MM-DD') from exc
        if through < JOINED_ON or through > today:
            raise CommandError(f'--through must be between {JOINED_ON} and {today}')

        new_credentials = []
        existing_accounts = []
        demo_count = 0
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
                if is_admin:
                    ray = user

            day = JOINED_ON
            while day <= through:
                day_number = (day - JOINED_ON).days
                events = [('visit', 'Dashboard visit (demo)', time(9, 0))]
                if day_number % 2 == 0:
                    events.append(('read', 'Alert review (demo)', time(9, 7)))
                if day_number % 3 == 0:
                    events.append(('auto_feed', 'Automatic feed trigger (demo)', time(9, 15)))
                for action, label, at_time in events:
                    record_id = f'demo-ray-goco-{day:%Y%m%d}-{action}'
                    if ActivityLog.objects.filter(is_simulated=True, record_id=record_id).exists():
                        continue
                    log = ActivityLog.objects.create(
                        actor=ray, username=ray.username, privileges=user_privileges(ray),
                        action=action, resource='demo_activity', record_id=record_id,
                        record_label=label, is_simulated=True,
                        changes=[{
                            'field': 'simulation', 'before': None,
                            'after': 'Demonstration record only; no real visit, alert read, or feed command occurred.',
                        }],
                    )
                    ActivityLog.objects.filter(pk=log.pk).update(
                        occurred_at=datetime.combine(day, at_time, tzinfo=MANILA),
                    )
                    demo_count += 1
                day += timedelta(days=1)

        for username, password in new_credentials:
            self.stdout.write(f'CREDENTIALS  username={username}  temporary_password={password}')
        for username in existing_accounts:
            self.stdout.write(f'EXISTING ACCOUNT  username={username}  password unchanged; join date unchanged')
        self.stdout.write(self.style.SUCCESS(
            f'Accounts ready: {len(PEOPLE)}. Simulated activity added: {demo_count}. '
            'Copy new passwords now; they are not stored in plain text.'
        ))
