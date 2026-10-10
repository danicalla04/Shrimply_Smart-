"""Capture successful website mutations and preserve actor/change snapshots."""
from contextvars import ContextVar
import json
from django.apps import apps
from django.contrib.auth.models import User
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models.signals import pre_save, post_save, pre_delete, post_delete, m2m_changed
from django.dispatch import receiver
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import ActivityLog
from .permissions import user_privileges, UPDATE_ACTIONS

_context = ContextVar('activity_log_context', default=None)
TRACKED = {'Season', 'HarvestEntry', 'HistorySettings', 'Threshold', 'SensorCalibration', 'Feeder', 'Report', 'Alert', 'FeedType', 'DailyGrowthMetric', 'SeasonHistory', 'SensorReading', 'WeatherForecast', 'FeedingLog', 'GrowthPrediction', 'WeatherPrediction'}
ROUTES = {'seasons': 'Season', 'harvest-entries': 'HarvestEntry', 'history-settings': 'HistorySettings', 'thresholds': 'Threshold', 'calibration': 'SensorCalibration', 'feeder': 'Feeder', 'reports': 'Report', 'alerts': 'Alert', 'feed-types': 'FeedType', 'growth-metrics': 'DailyGrowthMetric', 'growth-predictions': 'GrowthPrediction'}


def clean(value):
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items() if not any(word in str(key).lower() for word in ('password', 'token', 'secret', 'api_key'))}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value[:100]]
    if isinstance(value, str):
        return value[:2000]
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder, default=str))


def snapshot(instance):
    if isinstance(instance, User):
        result = {name: getattr(instance, name) for name in ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser')}
        result['privileges'] = user_privileges(instance)
        return result
    return {field.name: clean(getattr(instance, field.attname)) for field in instance._meta.concrete_fields if field.name not in ('id', 'created_at', 'updated_at', 'data', 'summary') and not any(word in field.name.lower() for word in ('password', 'token', 'secret', 'api_key'))}


def label(instance):
    return str(getattr(instance, 'username', None) or getattr(instance, 'name', None) or getattr(instance, 'title', None) or f'{instance._meta.verbose_name} #{instance.pk}')[:255]


def tracked(sender):
    return sender is User or (sender._meta.app_label == 'api' and sender.__name__ in TRACKED)


def capture(instance, before, after):
    context = _context.get()
    if context is None:
        return
    key = (instance._meta.label, str(instance.pk))
    previous = context['events'].get(key)
    context['events'][key] = {'resource': str(instance._meta.verbose_name), 'record_id': str(instance.pk), 'record_label': label(instance), 'before': previous['before'] if previous else before, 'after': after}


@receiver(pre_save, dispatch_uid='audit_pre_save')
def before_save(sender, instance, raw=False, **kwargs):
    context = _context.get()
    if context is None or raw or not tracked(sender):
        return
    previous = sender.objects.filter(pk=instance.pk).first() if instance.pk else None
    context['before'][id(instance)] = snapshot(previous) if previous else None


@receiver(post_save, dispatch_uid='audit_post_save')
def after_save(sender, instance, raw=False, **kwargs):
    context = _context.get()
    if context is None or raw or not tracked(sender):
        return
    capture(instance, context['before'].pop(id(instance), None), snapshot(instance))


@receiver(pre_delete, dispatch_uid='audit_pre_delete')
def before_delete(sender, instance, **kwargs):
    context = _context.get()
    if context is not None and tracked(sender):
        context['before'][id(instance)] = snapshot(instance)


@receiver(post_delete, dispatch_uid='audit_post_delete')
def after_delete(sender, instance, **kwargs):
    context = _context.get()
    if context is not None and tracked(sender):
        capture(instance, context['before'].pop(id(instance), None), None)


@receiver(m2m_changed, sender=User.groups.through, dispatch_uid='audit_user_privileges')
def privileges_changed(sender, instance, action, reverse=False, **kwargs):
    context = _context.get()
    if context is None or reverse or not isinstance(instance, User):
        return
    if action.startswith('pre_'):
        context['groups'][instance.pk] = snapshot(instance)
    elif action.startswith('post_'):
        capture(instance, context['groups'].pop(instance.pk, None), snapshot(instance))


def primary_records(request):
    parts = request.path.strip('/').split('/')
    name = ROUTES.get(parts[1] if len(parts) > 1 else '')
    if not name:
        return {}
    model = apps.get_model('api', name)
    queryset = model.objects.all()
    if len(parts) > 2 and parts[2].isdigit():
        queryset = queryset.filter(pk=parts[2])
    elif name == 'HistorySettings':
        queryset = queryset.filter(user=request.user)
    return {(model._meta.label, str(obj.pk)): (obj, snapshot(obj)) for obj in queryset}


class ActivityLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith('/api/') or (request.method in ('GET', 'HEAD', 'OPTIONS') and not request.path.rstrip('/').endswith(('/process_auto_feed', '/check_thresholds'))):
            return self.get_response(request)
        actor = getattr(request, '_force_auth_user', None) or request.user
        if not actor.is_authenticated:
            try:
                result = JWTAuthentication().authenticate(request)
                actor = result[0] if result else actor
            except AuthenticationFailed:
                return self.get_response(request)
        if not actor.is_authenticated:
            return self.get_response(request)
        context = {'events': {}, 'before': {}, 'groups': {}}
        token = _context.set(context)
        original_user = request.user
        request.user = actor
        privileges = user_privileges(actor)
        try:
            with transaction.atomic():
                initial = primary_records(request)
                response = self.get_response(request)
                if not 200 <= response.status_code < 300:
                    transaction.set_rollback(True)
                    return response
                final = primary_records(request)
                # Compare the primary resource too: QuerySet.update/delete and bulk writes do not emit every save signal.
                for key in initial.keys() | final.keys():
                    obj = (final.get(key) or initial[key])[0]
                    before = initial[key][1] if key in initial else None
                    after = final[key][1] if key in final else None
                    if before != after:
                        context['events'][key] = {'resource': str(obj._meta.verbose_name), 'record_id': str(obj.pk), 'record_label': label(obj), 'before': before, 'after': after}
                logs = []
                for event in context['events'].values():
                    before, after = event.pop('before'), event.pop('after')
                    if before == after:
                        continue
                    changes = [{'field': field, 'before': (before or {}).get(field), 'after': (after or {}).get(field)} for field in sorted((before or {}).keys() | (after or {}).keys()) if before is None or after is None or before.get(field) != after.get(field)]
                    logs.append(ActivityLog(actor=actor, username=actor.username, privileges=privileges, action='create' if before is None else 'delete' if after is None else 'update', changes=changes, **event))
                # Explicit commands can change a device without saving a tracked model.
                view = request.resolver_match.func if request.resolver_match else None
                operation = getattr(view, 'actions', {}).get(request.method.lower()) or getattr(view, '__name__', '')
                if not logs and operation in UPDATE_ACTIONS:
                    logs.append(ActivityLog(actor=actor, username=actor.username, privileges=privileges,
                        action='update', resource='operation', record_label=operation.replace('_', ' ').capitalize(),
                        changes=[{'field': 'operation', 'before': None, 'after': operation.replace('_', ' ')}]))
                ActivityLog.objects.bulk_create(logs)
                return response
        finally:
            request.user = original_user
            _context.reset(token)
