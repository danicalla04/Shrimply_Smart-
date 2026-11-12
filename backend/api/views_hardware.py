from datetime import timedelta

from django.http import HttpResponse
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_GET
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .hardware_status import assess_hardware_status
from .models import ActivityLog, HardwareCommand, HardwareTestState
from .permissions import user_privileges


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_hardware_command(request):
    if request.user.username != 'admin123' or not request.user.is_staff or not request.user.is_active:
        return Response({'detail': 'Only admin123 can control this hardware.'}, status=403)

    target = request.data.get('target')
    state = request.data.get('state')
    if target not in dict(HardwareCommand.TARGETS) or type(state) is not bool:
        return Response({'detail': 'Target must be LED1, LED2, LED3, BUZZER, or ALL; state must be true or false.'}, status=400)

    state_label = 'ON' if state else 'OFF'
    with transaction.atomic():
        command = HardwareCommand.objects.create(target=target, state=state, requested_by=request.user)
        ActivityLog.objects.create(
            actor=request.user, username=request.user.username,
            privileges=user_privileges(request.user), action='update',
            resource='hardware command', record_id=str(command.pk),
            record_label=f'Queued {target} {state_label}',
            changes=[{'field': 'state', 'before': None, 'after': state_label}],
        )
    return Response({'id': command.pk, 'target': target, 'state': state_label, 'queued': True}, status=201)


@require_GET
def poll_hardware_command(request):
    """Read-only plain text command feed for the ESP8266; no browser credentials needed."""
    if request.GET.get('latest') == '1':
        latest = HardwareCommand.objects.order_by('-pk').values_list('pk', flat=True).first() or 0
        return HttpResponse(f'id={latest}', content_type='text/plain')
    try:
        after = int(request.GET.get('after', '0'))
        if after < 0:
            raise ValueError
    except ValueError:
        return HttpResponse('Invalid after value', status=400, content_type='text/plain')
    command = HardwareCommand.objects.filter(pk__gt=after).first()
    if not command:
        return HttpResponse('NONE', content_type='text/plain')
    state = 'ON' if command.state else 'OFF'
    return HttpResponse(f'id={command.pk}&target={command.target}&state={state}', content_type='text/plain')


@api_view(['GET'])
@permission_classes([AllowAny])
def hardware_status(request):
    """Current automatic output state. The ESP8266 reads the compact response."""
    status = assess_hardware_status()
    if request.GET.get('format') == 'json':
        if not request.user.is_authenticated or request.user.username != 'admin123' or not request.user.is_staff:
            return HttpResponse('Forbidden', status=403)
        from django.http import JsonResponse
        return JsonResponse(status)
    return HttpResponse(f"color={status['color']}&buzzer={status['buzzer']}", content_type='text/plain')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_feeder_test_connection(request):
    if request.user.username != 'admin123' or not request.user.is_staff or not request.user.is_active:
        return Response({'detail': 'Only admin123 can test the feeder connection.'}, status=403)
    connected = request.data.get('connected')
    if type(connected) is not bool:
        return Response({'detail': 'connected must be true or false.'}, status=400)
    state, _ = HardwareTestState.objects.get_or_create(pk=1)
    state.feeder_connected_until = timezone.now() + timedelta(minutes=30) if connected else None
    state.updated_by = request.user
    state.save(update_fields=['feeder_connected_until', 'updated_by'])
    return Response(assess_hardware_status())
