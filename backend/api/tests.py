from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework.test import APITestCase


class AccountCreationTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user('account_admin', password='Admin-Example-7482', is_staff=True)
        self.member = User.objects.create_user('account_member', password='Member-Example-7482')
        self.payload = {
            'username': 'invited_user',
            'password': 'Invited-Example-7482',
            'password2': 'Invited-Example-7482',
            'email': 'invited@example.com',
        }

    def test_public_signup_is_denied(self):
        response = self.client.post(reverse('register'), self.payload)
        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(User.objects.filter(username='invited_user').exists())

    def test_regular_user_cannot_create_accounts(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(reverse('register'), self.payload)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username='invited_user').exists())

    def test_admin_creates_regular_account_without_changing_identity(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(reverse('register'), {**self.payload, 'is_staff': True, 'is_superuser': True})
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username='invited_user')
        self.assertTrue(user.check_password(self.payload['password']))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertNotIn('password', response.data)
        self.assertEqual(self.client.get(reverse('current_user')).data, {'username': 'account_admin', 'is_admin': True, 'privileges': {'create': True, 'update': True, 'delete': True}})

    def test_duplicate_username_and_mismatched_passwords_are_rejected(self):
        self.client.force_authenticate(self.admin)
        for payload in [
            {**self.payload, 'username': self.member.username},
            {**self.payload, 'password2': 'different-password'},
        ]:
            self.assertEqual(self.client.post(reverse('register'), payload).status_code, 400)
        self.assertFalse(User.objects.filter(username='invited_user').exists())

    def test_profile_requires_login_and_reports_regular_user(self):
        self.assertIn(self.client.get(reverse('current_user')).status_code, (401, 403))
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.get(reverse('current_user')).data, {'username': 'account_member', 'is_admin': False, 'privileges': {'create': False, 'update': False, 'delete': False}})


class RequestedAccountSeedTests(APITestCase):
    def test_accounts_and_password_reset_do_not_create_activity(self):
        from io import StringIO
        from zoneinfo import ZoneInfo
        from django.core.management import call_command
        from .models import ActivityLog
        from .permissions import user_privileges

        output = StringIO()
        call_command('seed_demo_access', stdout=output)
        old_ray_password = next(line.split('temporary_password=')[1] for line in output.getvalue().splitlines() if 'username=ray.goco ' in line)
        self.assertEqual(User.objects.count(), 5)
        ray = User.objects.get(username='ray.goco')
        self.assertTrue(ray.is_staff)
        self.assertFalse(ray.is_superuser)
        self.assertEqual(ray.date_joined.astimezone(ZoneInfo('Asia/Manila')).date().isoformat(), '2026-10-16')
        self.assertEqual(user_privileges(ray), {'create': True, 'update': True, 'delete': True})
        for username in ('leizl.reyes.abas', 'mark.royan', 'darwin.baculo', 'felix.flores'):
            user = User.objects.get(username=username)
            self.assertFalse(user.is_staff)
            self.assertTrue(user.is_active)
            self.assertEqual(user_privileges(user), {'create': False, 'update': False, 'delete': False})
            self.assertEqual(user.date_joined.astimezone(ZoneInfo('Asia/Manila')).date().isoformat(), '2026-10-16')
        self.assertEqual(ActivityLog.objects.count(), 0)

        call_command('seed_demo_access', stdout=StringIO())
        self.assertEqual(User.objects.count(), 5)
        self.assertEqual(ActivityLog.objects.count(), 0)

        reset_output = StringIO()
        call_command('seed_demo_access', reset_passwords=True, stdout=reset_output)
        self.assertEqual(reset_output.getvalue().count('CREDENTIALS  username='), 5)
        new_ray_password = next(line.split('temporary_password=')[1] for line in reset_output.getvalue().splitlines() if 'username=ray.goco ' in line)
        ray.refresh_from_db()
        self.assertFalse(ray.check_password(old_ray_password))
        self.assertTrue(ray.check_password(new_ray_password))
        self.assertEqual(ActivityLog.objects.count(), 0)


class TemporaryRayActivityTests(APITestCase):
    def test_fixture_is_removable_without_touching_real_activity(self):
        from io import StringIO
        from zoneinfo import ZoneInfo
        from django.core.management import call_command
        from .models import ActivityLog

        ray = User.objects.create_user('ray.goco', password='Ray-Example-7482', is_staff=True)
        real = ActivityLog.objects.create(
            actor=ray, username=ray.username, privileges={}, action='visit',
            resource='page', record_id='/dashboard', record_label='Opened Dashboard',
        )
        call_command('seed_ray_test_activity', stdout=StringIO())
        fixture = ActivityLog.objects.exclude(pk=real.pk)
        self.assertEqual(fixture.count(), 25)
        self.assertEqual(set(fixture.values_list('action', flat=True)), {'visit', 'read', 'update'})
        dates = {value.astimezone(ZoneInfo('Asia/Manila')).date().isoformat() for value in fixture.values_list('occurred_at', flat=True)}
        self.assertIn('2026-10-17', dates)
        self.assertIn('2026-11-07', dates)
        self.assertTrue(all(log.test_batch for log in fixture))

        self.client.force_authenticate(ray)
        response = self.client.get('/api/activity-logs/?username=ray.goco')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('test_batch', response.data['results'][0])

        call_command('seed_ray_test_activity', stdout=StringIO())
        self.assertEqual(ActivityLog.objects.count(), 26)
        call_command('seed_ray_test_activity', delete=True, stdout=StringIO())
        self.assertEqual(list(ActivityLog.objects.values_list('pk', flat=True)), [real.pk])


class HardwareCommandTests(APITestCase):
    def test_only_admin123_can_queue_output_commands_and_device_can_poll(self):
        from .models import ActivityLog, HardwareCommand

        admin123 = User.objects.create_user('admin123', password='Admin-Example-3812', is_staff=True)
        other_admin = User.objects.create_user('ray.goco', password='Ray-Example-3812', is_staff=True)
        url = '/api/hardware/commands/'
        poll_url = '/api/hardware/commands/poll/'

        self.assertIn(self.client.post(url, {'target': 'LED1', 'state': True}, format='json').status_code, (401, 403))
        self.client.force_authenticate(other_admin)
        self.assertEqual(self.client.post(url, {'target': 'LED1', 'state': True}, format='json').status_code, 403)
        self.client.force_authenticate(admin123)
        self.assertEqual(self.client.post(url, {'target': 'LED1', 'state': 'ON'}, format='json').status_code, 400)
        self.assertEqual(self.client.post(url, {'target': 'SERVO', 'state': True}, format='json').status_code, 400)
        self.assertFalse(HardwareCommand.objects.exists())

        first = self.client.post(url, {'target': 'LED1', 'state': True}, format='json')
        second = self.client.post(url, {'target': 'BUZZER', 'state': False}, format='json')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(ActivityLog.objects.filter(resource='hardware command', username='admin123').count(), 2)

        self.client.force_authenticate(None)
        first_id = first.data['id']
        second_id = second.data['id']
        self.assertEqual(self.client.get(poll_url).content.decode(), f'id={first_id}&target=LED1&state=ON')
        self.assertEqual(self.client.get(f'{poll_url}?after={first_id}').content.decode(), f'id={second_id}&target=BUZZER&state=OFF')
        self.assertEqual(self.client.get(f'{poll_url}?after={second_id}').content.decode(), 'NONE')
        self.assertEqual(self.client.get(f'{poll_url}?latest=1').content.decode(), f'id={second_id}')


class HardwareStatusTests(APITestCase):
    def setUp(self):
        from .models import SensorReading
        self.admin = User.objects.create_user('admin123', is_staff=True)
        self.reading = SensorReading.objects.create(temperature=27, ph=7.2, turbidity=5, tds=200)

    def status(self):
        response = self.client.get('/api/hardware/status/?format=json')
        self.assertEqual(response.status_code, 200, (response.status_code, response.get('Location'), response.content[:200]))
        return response.json()

    def test_saved_ranges_and_exclusive_colors(self):
        from .models import Threshold
        self.client.force_authenticate(self.admin)
        self.assertEqual((self.status()['color'], self.status()['buzzer']), ('BLUE', 'OFF'))
        Threshold.objects.create(parameter='ph', min_value=7.3, max_value=8.5)
        self.assertEqual((self.status()['color'], self.status()['buzzer'], self.status()['out_of_range_count']), ('YELLOW', 'OFF', 1))
        self.assertIn('pH 7.2 is outside 7.3 to 8.5.', self.status()['issues'])
        self.reading.temperature = 40
        self.reading.save()
        self.assertEqual((self.status()['color'], self.status()['buzzer'], self.status()['out_of_range_count']), ('YELLOW', 'OFF', 2))
        self.reading.turbidity = 100
        self.reading.save()
        self.assertEqual((self.status()['color'], self.status()['buzzer'], self.status()['out_of_range_count']), ('RED', 'ON', 3))
        self.reading.tds = 999
        self.reading.save()
        self.assertEqual((self.status()['color'], self.status()['buzzer'], self.status()['out_of_range_count']), ('RED', 'ON', 4))

    def test_feeder_level_and_connection_do_not_affect_lights(self):
        from .models import Feeder, FeederTelemetry
        self.client.force_authenticate(self.admin)
        Feeder.objects.create(capacity_current=0, low_percent=15)
        FeederTelemetry.objects.create(device_id='wemos-feeder', distance_cm=32)
        self.assertEqual((self.status()['color'], self.status()['buzzer']), ('BLUE', 'OFF'))
        FeederTelemetry.objects.all().delete()
        self.assertEqual((self.status()['color'], self.status()['buzzer']), ('BLUE', 'OFF'))

    def test_missing_and_stale_sensor_readings_are_red(self):
        from datetime import timedelta
        from django.utils import timezone
        self.client.force_authenticate(self.admin)
        self.reading.ph = None
        self.reading.save()
        self.assertEqual(self.status()['color'], 'RED')
        self.assertIn('pH reading is missing.', self.status()['issues'])
        self.reading.ph = 7.2
        self.reading.save()
        self.reading.__class__.objects.filter(pk=self.reading.pk).update(timestamp=timezone.now() - timedelta(seconds=31))
        self.assertEqual(self.status()['color'], 'RED')
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/hardware/status/').content.decode(), 'color=RED&buzzer=ON')
        self.assertEqual(self.client.get('/api/hardware/status/?format=json').status_code, 403)


class HardwareOutputReportTests(APITestCase):
    def test_device_report_is_visible_only_to_admin123(self):
        from .models import HardwareOutputState
        url = '/api/hardware/outputs/'
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'color': 'PURPLE', 'buzzer': 'OFF', 'mode': 'AUTO'}).status_code, 400)
        self.assertEqual(self.client.post(url, {'color': 'BLUE', 'buzzer': 'OFF', 'mode': 'AUTO'}).status_code, 200)
        self.assertEqual(self.client.post(url, {'color': 'RED', 'buzzer': 'ON', 'mode': 'MANUAL'}).status_code, 200)
        self.assertEqual(HardwareOutputState.objects.count(), 1)

        other_admin = User.objects.create_user('ray.goco', is_staff=True)
        self.client.force_authenticate(other_admin)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_authenticate(User.objects.create_user('admin123', is_staff=True))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['color'], 'RED')
        self.assertEqual(response.data['buzzer'], 'ON')
        self.assertEqual(response.data['mode'], 'MANUAL')
        self.assertIsNotNone(response.data['reported_at'])


class RemoveSimulatedActivityMigrationTests(TransactionTestCase):
    def test_migration_deletes_generated_history_and_keeps_real_history(self):
        old_target = [('api', '0029_activitylog_simulated_events')]
        new_target = [('api', '0030_remove_simulated_activity')]
        executor = MigrationExecutor(connection)
        executor.migrate(old_target)
        OldActivityLog = executor.loader.project_state(old_target).apps.get_model('api', 'ActivityLog')
        OldActivityLog.objects.create(
            username='ray.goco', privileges={}, action='visit', resource='demo_activity',
            record_id='demo-ray-goco-20261016-visit', is_simulated=True,
        )
        OldActivityLog.objects.create(
            username='admin123', privileges={}, action='update', resource='season',
            record_id='42', is_simulated=False,
        )

        executor = MigrationExecutor(connection)
        executor.migrate(new_target)
        NewActivityLog = executor.loader.project_state(new_target).apps.get_model('api', 'ActivityLog')
        self.assertEqual(list(NewActivityLog.objects.values_list('username', flat=True)), ['admin123'])


class AccountPrivilegeTests(APITestCase):
    def setUp(self):
        from .models import Season
        self.user = User.objects.create_user('privilege_member', password='Member-Example-9482')
        self.admin = User.objects.create_user('privilege_admin', password='Admin-Example-9482', is_staff=True)
        self.season = Season.objects.create(user=self.user, name='S1', start_date='2026-01-01')
        self.client.force_authenticate(self.user)

    def grant(self, **privileges):
        from .permissions import set_user_privileges
        set_user_privileges(self.user, privileges)

    def test_read_only_can_read_but_cannot_mutate_or_control(self):
        self.assertEqual(self.client.get('/api/seasons/').status_code, 200)
        for method, url in [
            ('post', '/api/seasons/start/'),
            ('patch', f'/api/seasons/{self.season.pk}/'),
            ('delete', f'/api/seasons/{self.season.pk}/'),
            ('post', '/api/thresholds/update_all/'),
            ('post', '/api/feeder/servo_on/'),
            ('post', '/api/buzzer/control/'),
            ('post', '/api/reports/generate_daily/'),
            ('get', '/api/feeder/process_auto_feed/'),
        ]:
            with self.subTest(url=url):
                self.assertEqual(getattr(self.client, method)(url, {}, format='json').status_code, 403)

    def test_update_does_not_grant_create_or_delete(self):
        self.grant(update=True)
        url = f'/api/seasons/{self.season.pk}/'
        self.assertEqual(self.client.patch(url, {'notes': 'Updated'}, format='json').status_code, 200)
        self.assertEqual(self.client.post('/api/seasons/start/', {}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)

    def test_create_does_not_grant_update_or_delete(self):
        self.grant(create=True)
        response = self.client.post('/api/seasons/', {'name': 'S2', 'start_date': '2026-02-01'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        url = f'/api/seasons/{self.season.pk}/'
        self.assertEqual(self.client.patch(url, {'notes': 'Forbidden'}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.assertEqual(self.client.post(f'{url}add_entry/', {'is_all': True}, format='json').status_code, 403)
        self.assertEqual(self.client.post('/api/feeder/servo_on/', {}, format='json').status_code, 403)
        self.assertEqual(self.client.post(reverse('register'), {}, format='json').status_code, 403)

    def test_delete_does_not_grant_create_or_update(self):
        self.grant(delete=True)
        url = f'/api/seasons/{self.season.pk}/'
        self.assertEqual(self.client.patch(url, {'notes': 'Forbidden'}, format='json').status_code, 403)
        self.assertEqual(self.client.post('/api/seasons/', {}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_delete_season_removes_its_name_entries_and_history(self):
        from .models import HarvestEntry, Season, SeasonHistory

        self.grant(delete=True)
        self.season.end_date = '2026-03-01'
        self.season.is_active = False
        self.season.save(update_fields=['end_date', 'is_active'])
        HarvestEntry.objects.create(season=self.season, date='2026-01-10', amount=5)
        matching_history = SeasonHistory.objects.create(
            season_name=self.season.name, start_date=self.season.start_date,
            end_date=self.season.end_date,
        )
        other_history = SeasonHistory.objects.create(
            season_name='Other season', start_date='2026-02-01',
        )

        self.assertEqual(self.client.delete(f'/api/seasons/{self.season.pk}/').status_code, 204)
        self.assertFalse(Season.objects.filter(pk=self.season.pk).exists())
        self.assertFalse(HarvestEntry.objects.filter(season_id=self.season.pk).exists())
        self.assertFalse(SeasonHistory.objects.filter(pk=matching_history.pk).exists())
        self.assertTrue(SeasonHistory.objects.filter(pk=other_history.pk).exists())
        self.assertFalse(Season.objects.filter(name='S1').exists())

    def test_admin_can_assign_privileges_and_default_is_read_only(self):
        self.client.force_authenticate(self.admin)
        base = {'password': 'Invited-Example-9482', 'password2': 'Invited-Example-9482'}
        response = self.client.post(reverse('register'), {**base, 'username': 'create_and_update', 'privileges': {'create': True, 'update': True}}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.client.force_authenticate(User.objects.get(username='create_and_update'))
        self.assertEqual(self.client.get(reverse('current_user')).data['privileges'], {'create': True, 'update': True, 'delete': False})
        self.client.force_authenticate(self.admin)
        response = self.client.post(reverse('register'), {**base, 'username': 'viewer_only'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['privileges'], {'create': False, 'update': False, 'delete': False})


class ActivityLogTests(APITestCase):
    def setUp(self):
        from .models import Season
        from .permissions import set_user_privileges
        self.admin = User.objects.create_user('log_admin', password='Admin-Example-3482', is_staff=True)
        self.member = User.objects.create_user('log_member', password='Member-Example-3482')
        set_user_privileges(self.member, {'create': True, 'update': True, 'delete': True})
        self.season = Season.objects.create(user=self.member, name='Original season', start_date='2026-01-01')
        self.client.force_authenticate(self.member)

    def test_create_update_delete_keep_actor_and_before_after(self):
        from .models import ActivityLog
        response = self.client.post('/api/seasons/', {'name': 'New season', 'start_date': '2026-02-01'}, format='json')
        self.assertEqual(response.status_code, 201)
        created = ActivityLog.objects.get(action='create', record_id=str(response.data['id']), resource='season')
        self.assertEqual(created.username, 'log_member')
        self.assertEqual(created.privileges, {'create': True, 'update': True, 'delete': True})
        url = f'/api/seasons/{self.season.pk}/'
        self.assertEqual(self.client.patch(url, {'name': 'Renamed season'}, format='json').status_code, 200)
        updated = ActivityLog.objects.get(action='update', record_id=str(self.season.pk), resource='season')
        self.assertIn({'field': 'name', 'before': 'Original season', 'after': 'Renamed season'}, updated.changes)
        self.assertEqual(self.client.delete(url).status_code, 204)
        deleted = ActivityLog.objects.get(action='delete', record_id=str(self.season.pk), resource='season')
        self.assertEqual(deleted.record_label, 'Renamed season')
        self.assertIn({'field': 'name', 'before': 'Renamed season', 'after': None}, deleted.changes)

    def test_page_visit_is_recorded_for_actual_authenticated_request_once_per_day(self):
        from .models import ActivityLog

        self.client.force_authenticate(None)
        self.assertIn(self.client.post('/api/page-visits/', {'path': '/dashboard'}, format='json').status_code, (401, 403))
        self.client.force_authenticate(self.member)
        response = self.client.post('/api/page-visits/', {'path': '/dashboard'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['recorded'])
        visit = ActivityLog.objects.get(action='visit')
        self.assertEqual(visit.username, 'log_member')
        self.assertEqual(visit.record_label, 'Opened Dashboard')
        self.assertEqual(visit.record_id, '/dashboard')
        self.assertFalse(self.client.post('/api/page-visits/', {'path': '/dashboard'}, format='json').data['recorded'])
        self.assertEqual(self.client.post('/api/page-visits/', {'path': '/unknown'}, format='json').status_code, 400)
        self.assertEqual(ActivityLog.objects.count(), 1)

        self.client.force_authenticate(self.admin)
        response = self.client.get('/api/activity-logs/?action=visit&username=log_member')
        self.assertEqual(response.data['count'], 1)

    def test_logs_and_account_privileges_are_admin_only(self):
        for url in ['/api/activity-logs/', '/api/account-access/']:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_authenticate(None)
        for url in ['/api/activity-logs/', '/api/account-access/']:
            self.assertIn(self.client.get(url).status_code, (401, 403))
        self.client.force_authenticate(self.admin)
        for url in ['/api/activity-logs/', '/api/account-access/']:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post('/api/activity-logs/', {}, format='json').status_code, 405)

    def test_account_creation_records_privileges_but_no_passwords(self):
        import json
        from .models import ActivityLog
        self.client.force_authenticate(self.admin)
        password = 'Private-Example-6482'
        response = self.client.post(reverse('register'), {'username': 'logged_invitation', 'password': password, 'password2': password, 'privileges': {'create': True}}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        entry = ActivityLog.objects.get(resource='user', record_id=str(User.objects.get(username='logged_invitation').pk))
        self.assertEqual(entry.username, 'log_admin')
        self.assertEqual(entry.action, 'create')
        self.assertIn({'field': 'privileges', 'before': None, 'after': {'create': True, 'update': False, 'delete': False}}, entry.changes)
        stored = json.dumps(entry.changes)
        self.assertNotIn(password, stored)
        self.assertNotIn('password', stored)
        self.assertNotIn('pbkdf2', stored)

    def test_failed_requests_do_not_create_activity(self):
        from .models import ActivityLog
        self.assertEqual(self.client.patch(f'/api/seasons/{self.season.pk}/', {'start_date': 'invalid-date'}, format='json').status_code, 400)
        self.assertFalse(ActivityLog.objects.exists())

    def test_bulk_season_update_is_recorded(self):
        from .models import ActivityLog
        response = self.client.post(f'/api/seasons/{self.season.pk}/add_entry/', {'date': '2026-03-01', 'amount': 200, 'unit': 'kg', 'is_all': True}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        entry = ActivityLog.objects.get(resource='season', record_id=str(self.season.pk), action='update')
        self.assertIn({'field': 'is_active', 'before': True, 'after': False}, entry.changes)
        self.assertTrue(ActivityLog.objects.filter(resource='harvest entry', action='create', username='log_member').exists())

    def test_admin_filters_logs_and_cannot_edit_or_delete_them(self):
        from .models import ActivityLog
        self.client.patch(f'/api/seasons/{self.season.pk}/', {'notes': 'Tracked change'}, format='json')
        self.client.force_authenticate(self.admin)
        response = self.client.get('/api/activity-logs/?action=update&username=log_member&search=Original')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        entry = ActivityLog.objects.get()
        self.assertEqual(self.client.patch(f'/api/activity-logs/{entry.pk}/', {}, format='json').status_code, 405)
        self.assertEqual(self.client.delete(f'/api/activity-logs/{entry.pk}/').status_code, 405)

    def test_log_keeps_username_when_actor_is_deleted(self):
        from .models import ActivityLog
        self.client.patch(f'/api/seasons/{self.season.pk}/', {'notes': 'Tracked change'}, format='json')
        entry = ActivityLog.objects.get(resource='season', action='update')
        self.member.delete()
        entry.refresh_from_db()
        self.assertIsNone(entry.actor)
        self.assertEqual(entry.username, 'log_member')


    def test_sensor_record_creation_is_logged(self):
        from .models import ActivityLog
        response = self.client.post('/api/sensors/', {'temperature': 29, 'ph': 7.5, 'turbidity': 10, 'tds': 800}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(ActivityLog.objects.filter(resource='sensor reading', action='create', username='log_member').exists())

    def test_jwt_user_is_identified_by_audit_middleware(self):
        from rest_framework_simplejwt.tokens import AccessToken
        from .models import ActivityLog
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.member)}')
        response = self.client.patch(f'/api/seasons/{self.season.pk}/', {'notes': 'JWT actor change'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ActivityLog.objects.get().username, 'log_member')


class SharedPondRecordTests(APITestCase):
    def setUp(self):
        from .models import Season, HarvestEntry, DailyGrowthMetric
        self.admin = User.objects.create_user('pond_admin', password='Admin-Example-5482', is_staff=True)
        self.member = User.objects.create_user('pond_member', password='Member-Example-5482')
        self.season = Season.objects.create(user=self.admin, name='Shared S1', start_date='2026-01-01', is_active=True)
        self.harvest = HarvestEntry.objects.create(season=self.season, date='2026-02-01', amount=200, unit='kg')
        self.metric = DailyGrowthMetric.objects.create(season=self.season, date='2026-01-02', shrimp_count=1000, avg_weight_grams=8)
        self.client.force_authenticate(self.member)

    def grant(self, **privileges):
        from .permissions import set_user_privileges
        set_user_privileges(self.member, privileges)

    def test_viewer_reads_shared_season_harvest_and_growth(self):
        response = self.client.get('/api/seasons/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.data], [self.season.pk])
        self.assertEqual(self.client.get('/api/seasons/current/').data['id'], self.season.pk)
        for url in [f'/api/seasons/{self.season.pk}/', f'/api/harvest-entries/{self.harvest.pk}/', f'/api/growth-metrics/{self.metric.pk}/', f'/api/seasons/{self.season.pk}/growth_predictions/']:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.patch(f'/api/seasons/{self.season.pk}/', {'notes': 'Forbidden'}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(f'/api/harvest-entries/{self.harvest.pk}/').status_code, 403)
        self.assertEqual(self.client.get('/api/activity-logs/').status_code, 403)

    def test_writer_updates_admin_record_and_log_identifies_actual_actor(self):
        from .models import ActivityLog
        self.grant(update=True)
        response = self.client.patch(f'/api/seasons/{self.season.pk}/', {'notes': 'Changed by member'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.season.refresh_from_db()
        self.assertEqual(self.season.user, self.admin)
        self.assertEqual(self.season.notes, 'Changed by member')
        entry = ActivityLog.objects.get(resource='season', action='update')
        self.assertEqual(entry.username, self.member.username)
        self.assertEqual(self.client.delete(f'/api/seasons/{self.season.pk}/').status_code, 403)

    def test_create_and_delete_privileges_work_on_shared_harvest(self):
        self.grant(create=True)
        response = self.client.post(f'/api/seasons/{self.season.pk}/add_entry/', {'date': '2026-02-02', 'amount': 50, 'unit': 'kg'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.season.refresh_from_db()
        self.assertEqual(self.season.total_harvest_kg, 250)
        self.assertEqual(self.client.delete(f'/api/harvest-entries/{self.harvest.pk}/').status_code, 403)
        self.grant(delete=True)
        self.assertEqual(self.client.delete(f'/api/harvest-entries/{self.harvest.pk}/').status_code, 204)
        self.season.refresh_from_db()
        self.assertEqual(self.season.total_harvest_kg, 50)

    def test_starting_shared_season_updates_existing_active_season_and_is_audited(self):
        from .models import ActivityLog
        self.grant(create=True)
        payload = {'name': 'Shared S2', 'start_date': '2026-03-01'}
        self.assertEqual(self.client.post('/api/seasons/start/', payload, format='json').status_code, 403)
        self.grant(create=True, update=True)
        response = self.client.post('/api/seasons/start/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.season.refresh_from_db()
        self.assertFalse(self.season.is_active)
        entry = ActivityLog.objects.get(resource='season', record_id=str(self.season.pk), action='update')
        self.assertEqual(entry.username, self.member.username)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/api/seasons/current/').data['id'], response.data['id'])

    def test_duplicate_season_names_are_rejected_across_creators(self):
        self.grant(create=True, update=True)
        payload = {'name': 'shared s1', 'start_date': '2026-03-01'}
        for url in ['/api/seasons/', '/api/seasons/start/']:
            self.assertEqual(self.client.post(url, payload, format='json').status_code, 400)
        self.season.refresh_from_db()
        self.assertTrue(self.season.is_active)


class AccountManagementTests(APITestCase):
    def setUp(self):
        from .models import Season, HarvestEntry, SeasonHistory
        from .permissions import set_user_privileges
        self.admin = User.objects.create_user('manager_admin', password='Admin-Example-8482', is_staff=True)
        self.member = User.objects.create_user('managed_member', password='Member-Example-8482', email='old@example.com')
        set_user_privileges(self.member, {'create': True, 'update': True, 'delete': True})
        self.season = Season.objects.create(user=self.member, name='Preserved season', start_date='2026-01-01')
        self.harvest = HarvestEntry.objects.create(season=self.season, date='2026-02-01', amount=200, unit='kg')
        self.history = SeasonHistory.objects.create(user=self.member, season_name=self.season.name, start_date='2026-01-01')
        self.client.force_authenticate(self.admin)
        self.url = f'/api/accounts/{self.member.pk}/'

    def test_admin_edits_profile_and_privileges_with_audit_details(self):
        from .models import ActivityLog
        response = self.client.patch(self.url, {'username': 'renamed_member', 'first_name': 'Dan', 'last_name': 'Updated', 'email': 'new@example.com', 'privileges': {'create': False, 'update': True, 'delete': False}}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['email'], 'new@example.com')
        self.assertEqual(response.data['name'], 'Dan Updated')
        self.assertEqual(response.data['privileges'], {'create': False, 'update': True, 'delete': False})
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password('Member-Example-8482'))
        self.assertFalse(self.member.is_staff)
        entry = ActivityLog.objects.get(resource='user', record_id=str(self.member.pk), action='update')
        self.assertEqual(entry.username, self.admin.username)
        self.assertIn({'field': 'email', 'before': 'old@example.com', 'after': 'new@example.com'}, entry.changes)
        self.assertIn({'field': 'privileges', 'before': {'create': True, 'update': True, 'delete': True}, 'after': {'create': False, 'update': True, 'delete': False}}, entry.changes)

    def test_regular_users_and_anonymous_cannot_manage_accounts(self):
        self.client.force_authenticate(self.member)
        for method in ['get', 'patch', 'delete']:
            self.assertEqual(getattr(self.client, method)(self.url, {}, format='json').status_code, 403)
        self.client.force_authenticate(None)
        self.assertIn(self.client.patch(self.url, {}, format='json').status_code, (401, 403))

    def test_revoking_privileges_blocks_existing_account(self):
        response = self.client.patch(self.url, {'privileges': {'create': False, 'update': False, 'delete': False}}, format='json')
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.get('/api/seasons/').status_code, 200)
        self.assertEqual(self.client.patch(f'/api/seasons/{self.season.pk}/', {'notes': 'Forbidden'}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(f'/api/harvest-entries/{self.harvest.pk}/').status_code, 403)

    def test_account_deletion_preserves_pond_records_and_activity(self):
        from .models import ActivityLog, HarvestEntry
        self.client.force_authenticate(self.member)
        self.client.patch(f'/api/seasons/{self.season.pk}/', {'notes': 'Before deleting user'}, format='json')
        old_log = ActivityLog.objects.get(resource='season', action='update')
        self.client.force_authenticate(self.admin)
        member_id = self.member.pk
        self.assertEqual(self.client.delete(self.url).status_code, 204)
        self.assertFalse(User.objects.filter(pk=member_id).exists())
        self.season.refresh_from_db()
        self.history.refresh_from_db()
        old_log.refresh_from_db()
        self.assertIsNone(self.season.user_id)
        self.assertIsNone(self.history.user_id)
        self.assertTrue(HarvestEntry.objects.filter(pk=self.harvest.pk).exists())
        self.assertIsNone(old_log.actor_id)
        self.assertEqual(old_log.username, 'managed_member')
        deleted = ActivityLog.objects.get(resource='user', record_id=str(member_id), action='delete')
        self.assertEqual(deleted.username, self.admin.username)
        self.assertEqual(deleted.record_label, 'managed_member')
        self.assertEqual(self.client.get(f'/api/seasons/{self.season.pk}/').status_code, 200)

    def test_self_deletion_deactivation_and_role_changes_are_blocked(self):
        url = f'/api/accounts/{self.admin.pk}/'
        self.assertEqual(self.client.delete(url).status_code, 400)
        self.assertEqual(self.client.patch(url, {'is_active': False}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(url, {'privileges': {'create': False}}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.url, {'is_staff': True}, format='json').status_code, 400)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_staff)
        current = next(row for row in self.client.get('/api/account-access/').data if row['id'] == self.admin.pk)
        self.assertTrue(current['is_current_user'])

    def test_invalid_email_and_duplicate_username_are_rejected(self):
        for changes in [{'email': 'invalid-email'}, {'username': self.admin.username}]:
            self.assertEqual(self.client.patch(self.url, changes, format='json').status_code, 400)
        self.member.refresh_from_db()
        self.assertEqual(self.member.email, 'old@example.com')
        self.assertEqual(self.member.username, 'managed_member')


class ConnectionAlertRecoveryTests(APITestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user('connection_viewer')
        self.client.force_authenticate(self.user)

    def alert(self, parameter, value=None):
        from .models import Alert
        return Alert.objects.create(parameter=parameter, severity='critical', value=value, message='Disconnected')

    def test_fresh_sensor_packet_marks_only_recovered_disconnects_read(self):
        from .models import Alert, SensorReading
        offline = self.alert('sensor_offline')
        temperature = self.alert('temperature')
        missing_ph = self.alert('ph')
        unsafe_temperature = self.alert('temperature', value=40)
        original_time = offline.timestamp
        SensorReading.objects.create(temperature=0, ph=None, turbidity=10, tds=800)
        for alert in (offline, temperature, missing_ph, unsafe_temperature):
            alert.refresh_from_db()
        self.assertTrue(offline.resolved)
        self.assertTrue(temperature.resolved)
        self.assertFalse(missing_ph.resolved)
        self.assertFalse(unsafe_temperature.resolved)
        self.assertEqual(offline.timestamp, original_time)
        self.assertEqual(Alert.objects.count(), 4)
        self.assertIn('Automatically marked as read', offline.message)

    def test_ultrasonic_recovery_preserves_low_feed_alert_and_history(self):
        from .models import Alert, FeederTelemetry
        connection = self.alert('feeder_connection')
        low_feed = self.alert('feeder_level', value=35)
        FeederTelemetry.objects.create(distance_cm=None)
        connection.refresh_from_db()
        self.assertFalse(connection.resolved)
        FeederTelemetry.objects.create(distance_cm=35)
        connection.refresh_from_db()
        low_feed.refresh_from_db()
        self.assertTrue(connection.resolved)
        self.assertFalse(low_feed.resolved)
        self.assertEqual(Alert.objects.count(), 2)

    def test_stale_packets_do_not_resolve_alerts(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import SensorReading, FeederTelemetry
        from .alert_service import AlertService
        reading = SensorReading.objects.create(temperature=28, ph=7, turbidity=10, tds=800)
        telemetry = FeederTelemetry.objects.create(distance_cm=23)
        reading.timestamp = telemetry.timestamp = timezone.now() - timedelta(minutes=2)
        offline = self.alert('sensor_offline')
        connection = self.alert('feeder_connection')
        AlertService.recover_alerts(reading, telemetry)
        offline.refresh_from_db()
        connection.refresh_from_db()
        self.assertFalse(offline.resolved)
        self.assertFalse(connection.resolved)

    def test_alert_list_detects_php_inserts_and_summary_counts_only_unread(self):
        from .models import SensorReading, FeederTelemetry, Alert
        offline = self.alert('sensor_offline')
        connection = self.alert('feeder_connection')
        # Bulk inserts model the PHP upload path, which bypasses post_save signals.
        SensorReading.objects.bulk_create([SensorReading(temperature=28, ph=7, turbidity=10, tds=800)])
        FeederTelemetry.objects.bulk_create([FeederTelemetry(distance_cm=23)])
        response = self.client.get('/api/alerts/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)
        self.assertTrue(all(alert['resolved'] for alert in response.data['results']))
        self.assertEqual(Alert.objects.filter(resolved=False).count(), 0)
        summary = self.client.get('/api/alerts/summary/')
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.data['total'], 0)

    def test_new_disconnection_after_recovery_creates_new_unread_alert(self):
        from unittest.mock import patch
        from .models import SensorReading, Alert
        from .alert_service import AlertService
        previous = self.alert('ph')
        SensorReading.objects.create(temperature=28, ph=7, turbidity=10, tds=800)
        missing = SensorReading.objects.create(temperature=28, ph=None, turbidity=10, tds=800)
        with patch.object(AlertService, 'notify_alert_async'):
            AlertService.check_disconnected_sensors(missing)
        previous.refresh_from_db()
        self.assertTrue(previous.resolved)
        self.assertEqual(Alert.objects.filter(parameter='ph', resolved=False).count(), 1)
        self.assertEqual(Alert.objects.filter(parameter='ph').count(), 2)


class WaterQualitySettingsRangeTests(APITestCase):
    def setUp(self):
        from .models import Threshold

        self.client.force_authenticate(User.objects.create_user('water_quality_viewer'))
        self.ranges = {
            'temperature': (25, 30), 'ph': (6.5, 8.5),
            'turbidity': (1, 25), 'tds': (20, 325),
        }
        for parameter, (minimum, maximum) in self.ranges.items():
            Threshold.objects.create(parameter=parameter, min_value=minimum, max_value=maximum)

    def test_all_readings_within_settings_ranges_are_good_even_if_model_disagrees(self):
        from unittest.mock import patch
        from .models import SensorReading

        SensorReading.objects.bulk_create([
            SensorReading(temperature=25, ph=7.2, turbidity=1, tds=20),
        ])
        model_result = {'status': 'poor', 'ml_class': 'Severe', 'quality_score': 0}
        with patch('api.ml_water_quality.predict_water_quality', return_value=model_result):
            response = self.client.get('/api/water-quality/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'good')
        self.assertEqual(response.data['threshold_score'], 100)
        self.assertEqual(response.data['issues'], [])
        for parameter in self.ranges:
            self.assertEqual(response.data['parameters'][parameter]['status'], 'optimal')
            self.assertEqual(response.data['parameters'][parameter]['label_tone'], 'good')

    def test_reading_outside_saved_range_is_poor(self):
        from unittest.mock import patch
        from .models import SensorReading

        SensorReading.objects.bulk_create([
            SensorReading(temperature=26, ph=6.4, turbidity=2, tds=25),
        ])
        with patch('api.ml_water_quality.predict_water_quality', return_value=None):
            response = self.client.get('/api/water-quality/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'poor')
        self.assertEqual(response.data['parameters']['ph']['label_tone'], 'bad')
        self.assertEqual(response.data['threshold_score'], 75)


class RangeAlertRecoveryTests(APITestCase):
    def setUp(self):
        from django.core.cache import cache
        from .models import Threshold
        cache.clear()
        self.ranges = {'temperature': (25, 32), 'ph': (6, 9), 'turbidity': (0, 20), 'tds': (500, 1200)}
        for param, (low, high) in self.ranges.items():
            Threshold.objects.create(parameter=param, min_value=low, max_value=high)
        self.user = User.objects.create_user('range_viewer')
        self.client.force_authenticate(self.user)

    def alert(self, parameter, value, severity='warning'):
        from .models import Alert
        return Alert.objects.create(parameter=parameter, value=value, severity=severity, message='Out of range')

    def test_normal_reading_resolves_all_severities_and_preserves_history(self):
        from .models import SensorReading, Alert
        alerts = [self.alert(param, high + 10, severity) for param, (_, high) in self.ranges.items() for severity in ('low', 'high', 'warning', 'critical')]
        originals = [(alert.pk, alert.value, alert.timestamp) for alert in alerts]
        SensorReading.objects.create(temperature=25, ph=9, turbidity=0, tds=1200)
        self.assertEqual(Alert.objects.count(), 16)
        self.assertFalse(Alert.objects.filter(resolved=False).exists())
        for pk, value, timestamp in originals:
            alert = Alert.objects.get(pk=pk)
            self.assertEqual((alert.value, alert.timestamp), (value, timestamp))
            self.assertIn('within range', alert.message)

    def test_out_of_range_null_and_stale_values_leave_alerts_unread(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import SensorReading, Alert
        from .alert_service import AlertService
        for param in self.ranges:
            self.alert(param, 99)
        SensorReading.objects.create(temperature=40, ph=None, turbidity=21, tds=400)
        self.assertEqual(Alert.objects.filter(resolved=False).count(), 4)
        reading = SensorReading(temperature=28, ph=7, turbidity=10, tds=800, timestamp=timezone.now() - timedelta(minutes=2))
        AlertService.recover_alerts(sensor_reading=reading)
        self.assertEqual(Alert.objects.filter(resolved=False).count(), 4)

    def test_php_readings_recover_matching_ranges_on_summary(self):
        from .models import SensorReading
        temperature = self.alert('temperature', 40)
        ph = self.alert('ph', 10)
        SensorReading.objects.bulk_create([SensorReading(temperature=28, ph=10, turbidity=10, tds=800)])
        response = self.client.get('/api/alerts/summary/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total'], 1)
        temperature.refresh_from_db()
        ph.refresh_from_db()
        self.assertTrue(temperature.resolved)
        self.assertFalse(ph.resolved)

    def test_new_range_breach_after_recovery_creates_new_alert(self):
        from unittest.mock import patch
        from .models import SensorReading, Alert
        from .alert_service import AlertService
        previous = self.alert('temperature', 40)
        SensorReading.objects.create(temperature=28, ph=7, turbidity=10, tds=800)
        unsafe = SensorReading.objects.create(temperature=40, ph=7, turbidity=10, tds=800)
        with patch.object(AlertService, 'notify_alert_async'):
            AlertService.check_reading_and_create_alerts(unsafe)
        previous.refresh_from_db()
        self.assertTrue(previous.resolved)
        self.assertEqual(Alert.objects.filter(parameter='temperature', resolved=False).count(), 1)
        self.assertEqual(Alert.objects.filter(parameter='temperature').count(), 2)

    def test_feeder_level_recovers_only_below_low_distance(self):
        from .models import FeederTelemetry
        alert = self.alert('feeder_level', 35)
        for distance in (None, 32, 35):
            FeederTelemetry.objects.create(distance_cm=distance)
            alert.refresh_from_db()
            self.assertFalse(alert.resolved)
        FeederTelemetry.objects.create(distance_cm=23)
        alert.refresh_from_db()
        self.assertTrue(alert.resolved)
        self.assertEqual(alert.value, 35)

    def test_feeder_capacity_recovers_after_refill(self):
        from .models import Feeder
        feeder = Feeder.objects.create(capacity_max=1000, capacity_current=100, low_percent=15)
        alert = self.alert('feeder_capacity', 10)
        feeder.capacity_current = 150
        feeder.save()
        alert.refresh_from_db()
        self.assertFalse(alert.resolved)
        feeder.capacity_current = 1000
        feeder.save()
        alert.refresh_from_db()
        self.assertTrue(alert.resolved)
        self.assertEqual(alert.value, 10)
