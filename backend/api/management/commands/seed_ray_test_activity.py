"""Temporary Ray Goco activity fixture for testing the administrator log screen."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import ActivityLog, Threshold
from api.permissions import user_privileges


MANILA = ZoneInfo('Asia/Manila')
START = date(2026, 10, 17)
END = date(2026, 11, 7)
BATCH = 'ray-goco-ui-test-20261017-20261107'

# These are illustrative records for UI testing. They do not change thresholds or alerts.
SETTING_EVENTS = {
    2: ('ph', 'min_value', 6.5, 6.7),
    5: ('temperature', 'max_value', 32.0, 31.5),
    9: ('turbidity', 'max_value', 25.0, 20.0),
    13: ('ph', 'max_value', 8.5, 8.4),
    17: ('tds', 'max_value', 1200.0, 1100.0),
    20: ('ph', 'min_value', 6.7, 6.5),
}


class Command(BaseCommand):
    help = 'Add removable Ray Goco test activity from October 17 to November 7, 2026.'

    def add_arguments(self, parser):
        parser.add_argument('--delete', action='store_true', help='Remove only records created by this test fixture.')

    def handle(self, *args, **options):
        if options['delete']:
            count, _ = ActivityLog.objects.filter(test_batch=BATCH).delete()
            self.stdout.write(self.style.SUCCESS(f'Removed {count} Ray Goco test activity records.'))
            return

        ray = User.objects.filter(username__iexact='ray.goco').first()
        if ray is None:
            raise CommandError('ray.goco does not exist. Run seed_demo_access first.')

        with transaction.atomic():
            existing = ActivityLog.objects.filter(test_batch=BATCH).count()
            if existing:
                self.stdout.write(f'Test activity already exists: {existing} records. Use --delete to remove it.')
                return

            threshold_ids = {
                parameter: Threshold.objects.filter(parameter=parameter).values_list('pk', flat=True).first()
                for parameter in {item[0] for item in SETTING_EVENTS.values()}
            }
            count = 0
            day = START
            while day <= END:
                index = (day - START).days
                events = []
                if index % 2 == 0:
                    events.append((
                        'visit', 'page', '/dashboard', 'Opened Dashboard',
                        [{'field': 'page', 'before': None, 'after': '/dashboard'}],
                        time(8 + index % 3, 12 + index % 37),
                    ))
                if index % 3 == 0:
                    events.append((
                        'read', 'page', '/alerts', 'Reviewed alert center',
                        [{'field': 'page', 'before': None, 'after': '/alerts'}],
                        time(10 + index % 3, 5 + index % 43),
                    ))
                if index in SETTING_EVENTS:
                    parameter, field, before, after = SETTING_EVENTS[index]
                    events.append((
                        'update', 'threshold', str(threshold_ids[parameter] or parameter),
                        f'{parameter.upper() if parameter == "tds" else parameter.capitalize()} threshold',
                        [{'field': field, 'before': before, 'after': after}],
                        time(14 + index % 3, 8 + index % 41),
                    ))

                for action, resource, record_id, label, changes, at_time in events:
                    log = ActivityLog.objects.create(
                        actor=ray, username=ray.username, privileges=user_privileges(ray),
                        action=action, resource=resource, record_id=record_id,
                        record_label=label, changes=changes, test_batch=BATCH,
                    )
                    ActivityLog.objects.filter(pk=log.pk).update(
                        occurred_at=datetime.combine(day, at_time, tzinfo=MANILA),
                    )
                    count += 1
                day += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(
            f'Created {count} temporary Ray Goco test activity records for {START} to {END}. '
            'Run seed_ray_test_activity --delete when testing is finished.'
        ))
