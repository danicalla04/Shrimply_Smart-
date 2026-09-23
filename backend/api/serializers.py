from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import (
    SensorReading, Threshold, SensorCalibration, Alert, Feeder, FeedingLog, Report,
    WeatherForecast, Season, HarvestEntry, SeasonHistory, HistorySettings,
    FeederTelemetry, FeedType, DailyGrowthMetric, GrowthPrediction,
)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True, label='Confirm password')

    class Meta:
        model = User
        fields = ('username', 'password', 'password2', 'email', 'first_name', 'last_name')

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user

class SensorReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorReading
        fields = '__all__'


class ThresholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Threshold
        fields = '__all__'


class SensorCalibrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorCalibration
        fields = '__all__'

class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = '__all__'

class FeedingLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedingLog
        fields = '__all__'


class FeederTelemetrySerializer(serializers.ModelSerializer):
    class Meta:
        model = FeederTelemetry
        fields = '__all__'

class FeederSerializer(serializers.ModelSerializer):
    feeding_logs = FeedingLogSerializer(many=True, read_only=True)
    next_feed_time = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Feeder
        fields = '__all__'

    def get_next_feed_time(self, obj):
        return obj.get_next_feed_time()

    def get_status(self, obj):
        from django.utils import timezone
        now = timezone.now()

        if not obj.auto_enabled:
            return 'manual'

        if obj.next_feed_at and obj.next_feed_at > now:
            return 'scheduled'
        else:
            return 'due'

class ReportSerializer(serializers.ModelSerializer):
    duration_days = serializers.SerializerMethodField()
    
    class Meta:
        model = Report
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'generated_at']
    
    def get_duration_days(self, obj):
        if obj.start_date and obj.end_date:
            return (obj.end_date - obj.start_date).days
        return 0
    
    def create(self, validated_data):
        report = Report.objects.create(**validated_data)
        report.generate_summary()
        report.generate_insights()
        report.status = 'completed'
        from django.utils import timezone
        report.generated_at = timezone.now()
        report.save()
        return report

class WeatherForecastSerializer(serializers.ModelSerializer):
    forecast_type_display = serializers.CharField(source='get_forecast_type_display', read_only=True)
    temperature_impact_display = serializers.CharField(source='get_temperature_impact_display', read_only=True)
    rain_impact_display = serializers.CharField(source='get_rain_impact_display', read_only=True)
    wind_impact_display = serializers.CharField(source='get_wind_impact_display', read_only=True)
    
    class Meta:
        model = WeatherForecast
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    def to_representation(self, instance):
        """Customize the output format"""
        data = super().to_representation(instance)
        
        # Add computed fields
        data['forecast_for'] = instance.forecast_date.strftime('%Y-%m-%d')
        data['has_rain'] = instance.precipitation > 0
        data['is_extreme_temp'] = instance.temperature > 32 or instance.temperature < 20
        
        return data


# ── Season / Harvest serializers ──────────────────────────────────────

class HarvestEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = HarvestEntry
        fields = ['id', 'season', 'date', 'amount', 'unit', 'note', 'is_all', 'created_at']
        read_only_fields = ['id', 'created_at']


class SeasonSerializer(serializers.ModelSerializer):
    days_active = serializers.SerializerMethodField()

    class Meta:
        model = Season
        fields = [
            'id', 'name', 'start_date', 'end_date', 'is_active',
            'total_harvest_kg', 'harvest_count', 'entry_count',
            'stocking_density', 'initial_shrimp_quantity',
            'current_shrimp_quantity', 'average_shrimp_weight_grams',
            'notes', 'user', 'days_active', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'total_harvest_kg', 'harvest_count',
            'entry_count', 'created_at', 'updated_at',
        ]

    def get_days_active(self, obj):
        from django.utils import timezone
        end = obj.end_date or timezone.now().date()
        # Same-day season should show 1 day active, not 0
        return max(1, (end - obj.start_date).days + 1)


class SeasonHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SeasonHistory
        fields = '__all__'
        read_only_fields = fields


class HistorySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistorySettings
        fields = ['id', 'harvest_lead_days', 'harvest_time', 'notification_email', 'days_before_notification', 'user']
        read_only_fields = ['id', 'user']


class ReportGenerateSerializer(serializers.Serializer):
    """Write-only serializer for custom report generation."""
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    report_type = serializers.ChoiceField(
        choices=['daily', 'weekly', 'monthly', 'custom', 'seasonal'], default='custom',
    )


# ── Growth & Feed serializers ──────────────────────────────────────

class FeedTypeSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = FeedType
        fields = [
            'id', 'name', 'category', 'category_display', 'protein_percent', 'fat_percent',
            'fiber_percent', 'size_microns', 'target_min_weight_grams', 'target_max_weight_grams',
            'cost_per_kg', 'manufacturer', 'notes', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DailyGrowthMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyGrowthMetric
        fields = [
            'id', 'season', 'date', 'shrimp_count', 'avg_weight_grams', 'daily_weight_gain_grams',
            'daily_mortality_percent', 'feed_amount_grams', 'water_temperature', 'water_ph',
            'turbidity', 'dissolved_oxygen', 'tds', 'weather_condition', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class GrowthPredictionSerializer(serializers.ModelSerializer):
    recommendation_parsed = serializers.SerializerMethodField()
    predicted_avg_weight_base_grams = serializers.SerializerMethodField()

    class Meta:
        model = GrowthPrediction
        fields = [
            'id', 'season', 'prediction_date', 'forecast_date', 'predicted_avg_weight_grams',
            'predicted_avg_weight_base_grams',
            'predicted_shrimp_count', 'predicted_survival_rate_percent', 'estimated_harvest_date',
            'confidence_score', 'recommendation', 'recommendation_parsed', 'model_version',
            'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_recommendation_parsed(self, obj):
        from .ml_shrimp_growth import parse_growth_recommendation
        return parse_growth_recommendation(obj.recommendation)

    def get_predicted_avg_weight_base_grams(self, obj):
        from .ml_shrimp_growth import parse_growth_recommendation
        parsed = parse_growth_recommendation(obj.recommendation)
        if parsed and parsed.get('base_abw') is not None:
            return parsed['base_abw']
        return None
