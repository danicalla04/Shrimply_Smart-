from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers, viewsets, mixins, status
from rest_framework.exceptions import ValidationError
from django.db import transaction
from .serializers import PrivilegesSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import ActivityLog
from .permissions import user_privileges, set_user_privileges


PAGE_LABELS = {
    '/dashboard': 'Dashboard',
    '/alerts': 'Alert center',
    '/feeding': 'Feeding',
    '/ponds': 'Ponds',
    '/water-quality': 'Water quality',
    '/analytics': 'Analytics',
    '/history': 'History',
    '/settings': 'Settings',
    '/weather': 'Weather',
    '/reports': 'Reports',
    '/logs': 'Logs',
    '/hardware-controls': 'Hardware Controls',
}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def record_page_visit(request):
    """Record a page actually opened by the authenticated website user."""
    path = request.data.get('path')
    if path not in PAGE_LABELS:
        raise ValidationError({'path': 'Unknown page.'})
    today = timezone.localdate()
    existing = ActivityLog.objects.filter(
        actor=request.user, action='visit', resource='page', record_id=path,
        occurred_at__date=today,
    ).exists()
    if not existing:
        ActivityLog.objects.create(
            actor=request.user, username=request.user.username,
            privileges=user_privileges(request.user), action='visit',
            resource='page', record_id=path, record_label=f'Opened {PAGE_LABELS[path]}',
            changes=[{'field': 'page', 'before': None, 'after': path}],
        )
    return Response({'recorded': not existing})


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = ('id', 'username', 'privileges', 'action', 'resource', 'record_id', 'record_label', 'changes', 'occurred_at')


class LogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = LogPagination

    def get_queryset(self):
        queryset = ActivityLog.objects.all()
        params = self.request.query_params
        if params.get('action') in ('create', 'update', 'delete', 'visit', 'read'):
            queryset = queryset.filter(action=params['action'])
        if params.get('username'):
            queryset = queryset.filter(username=params['username'])
        if params.get('search'):
            query = params['search'][:150]
            queryset = queryset.filter(Q(username__icontains=query) | Q(record_label__icontains=query) | Q(resource__icontains=query))
        return queryset


class UserAccountSerializer(serializers.ModelSerializer):
    privileges = PrivilegesSerializer(required=False)
    name = serializers.CharField(source='get_full_name', read_only=True)
    is_admin = serializers.BooleanField(source='is_staff', read_only=True)
    is_current_user = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 'name', 'is_admin', 'is_active', 'is_current_user', 'date_joined', 'privileges')
        read_only_fields = ('id', 'name', 'is_admin', 'is_current_user', 'date_joined')

    def get_is_current_user(self, obj):
        return obj.pk == self.context['request'].user.pk

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['privileges'] = user_privileges(instance)
        return data

    def validate(self, attrs):
        allowed = {'username', 'first_name', 'last_name', 'email', 'is_active', 'privileges'}
        unknown = set(self.initial_data) - allowed
        if unknown:
            raise serializers.ValidationError({field: 'This field cannot be changed.' for field in unknown})
        if self.instance.is_staff and 'privileges' in attrs:
            raise serializers.ValidationError({'privileges': 'Administrator accounts retain full access.'})
        if attrs.get('is_active') is False and self.instance.pk == self.context['request'].user.pk:
            raise serializers.ValidationError({'is_active': 'You cannot deactivate your own account.'})
        if attrs.get('is_active') is False and self.instance.is_staff and not User.objects.filter(is_staff=True, is_active=True).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError({'is_active': 'At least one active administrator must remain.'})
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        privileges = validated_data.pop('privileges', None)
        instance = super().update(instance, validated_data)
        if privileges is not None:
            set_user_privileges(instance, {**user_privileges(instance), **privileges})
        return instance


class UserAccountViewSet(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = User.objects.all()
    serializer_class = UserAccountSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        # Lock admin accounts while validating changes that affect access.
        list(User.objects.select_for_update().filter(is_staff=True, is_active=True).values_list('pk', flat=True))
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        list(User.objects.select_for_update().filter(is_staff=True, is_active=True).values_list('pk', flat=True))
        account = self.get_object()
        if account.pk == request.user.pk:
            raise ValidationError('You cannot delete your own account.')
        if account.is_staff and account.is_active and not User.objects.filter(is_staff=True, is_active=True).exclude(pk=account.pk).exists():
            raise ValidationError('At least one active administrator must remain.')
        account.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def account_access(request):
    accounts = User.objects.prefetch_related('groups').order_by('username')
    return Response(UserAccountSerializer(accounts, many=True, context={'request': request}).data)
