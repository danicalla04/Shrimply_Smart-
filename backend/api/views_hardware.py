from django.http import HttpResponse
from django.db import transaction
from django.views.decorators.http import require_GET
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ActivityLog, HardwareCommand
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
