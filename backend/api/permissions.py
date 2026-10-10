from django.contrib.auth.models import Group
from rest_framework.permissions import BasePermission, SAFE_METHODS

PRIVILEGES = ('create', 'update', 'delete')
GROUP_PREFIX = 'shrimply_access_'
UPDATE_ACTIONS = {
    'update_all', 'update_settings', 'resolve', 'resolve_all', 'end',
    'feed_once', 'dummy_feed', 'refill', 'toggle_auto', 'servo_schedule',
    'servo_on', 'servo_off', 'apply_ml_today_feed', 'calculate_feeding_adjustment',
    'regenerate', 'regenerate_growth_predictions', 'email', 'process_auto_feed',
    'check_thresholds', 'control_buzzer', 'send_harvest_reminder', 'add_growth_metric',
}
DEVICE_ENDPOINTS = {'update_sensors', 'update_feeder_telemetry', 'device_readings'}


def user_privileges(user):
    if user.is_staff:
        return {key: True for key in PRIVILEGES}
    groups = set(user.groups.values_list('name', flat=True))
    return {key: GROUP_PREFIX + key in groups for key in PRIVILEGES}


def set_user_privileges(user, privileges):
    user.groups.remove(*user.groups.filter(name__in=[GROUP_PREFIX + key for key in PRIVILEGES]))
    for key in PRIVILEGES:
        if privileges.get(key, False):
            group, _ = Group.objects.get_or_create(name=GROUP_PREFIX + key)
            user.groups.add(group)


class AccountPrivileges(BasePermission):
    message = 'Your account does not have permission to perform this action.'

    def has_permission(self, request, view):
        action = getattr(view, 'action', None) or view.__class__.__name__
        # Device ingestion keeps its existing authentication behavior.
        if action in DEVICE_ENDPOINTS or action == 'telemetry':
            return True
        required = None
        if action in UPDATE_ACTIONS:
            required = 'update'
        elif request.method in SAFE_METHODS:
            return True
        elif request.method == 'DELETE':
            required = 'delete'
        elif request.method in ('PUT', 'PATCH'):
            required = 'update'
        elif request.method == 'POST':
            required = 'update' if view.__class__.__name__ == 'HistorySettingsViewSet' else 'create'
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        privileges = user_privileges(request.user)
        if action == 'start':
            from .models import Season
            if Season.objects.filter(is_active=True).exists():
                return privileges['create'] and privileges['update']
        if action == 'add_entry' and request.data.get('is_all'):
            return privileges['create'] and privileges['update']
        return bool(privileges.get(required, False))
