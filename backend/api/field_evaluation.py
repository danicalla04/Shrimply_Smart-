"""
Field Evaluation Data Collection & Analysis Module
Tracks weather forecast accuracy, water quality validation, feeder performance, and system reliability
Implements logging infrastructure for 12-week pond environment testing
"""

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
import json
from pathlib import Path


# ============================================================================
# DATABASE MODELS FOR FIELD EVALUATION
# ============================================================================

class FieldEvaluation_WeatherForecast(models.Model):
    """Daily weather forecast vs. actual observations for accuracy evaluation"""
    
    LOCATION_CHOICES = [
        ('calapan', 'Calapan, Oriental Mindoro'),
        ('pinamalayan', 'Pinamalayan, Oriental Mindoro'),
        ('san_carlos', 'San Carlos, Pangasinan'),
        ('bacolod', 'Bacolod, Negros Occidental'),
        ('cebu_city', 'Cebu City, Cebu'),
        ('davao_city', 'Davao City, Davao del Sur'),
    ]
    
    location = models.CharField(max_length=50, choices=LOCATION_CHOICES, db_index=True)
    forecast_date = models.DateField(db_index=True)
    forecast_issued_at = models.DateTimeField()
    day_offset = models.IntegerField(help_text="1=next day, 2=2 days out, etc.")
    
    # Temperature
    predicted_temp = models.FloatField(null=True, blank=True, help_text="°C")
    actual_temp = models.FloatField(null=True, blank=True, help_text="°C")
    temp_error = models.FloatField(null=True, blank=True, help_text="Actual - Predicted (°C)")
    
    # Humidity
    predicted_humidity = models.FloatField(null=True, blank=True, help_text="%")
    actual_humidity = models.FloatField(null=True, blank=True, help_text="%")
    humidity_error = models.FloatField(null=True, blank=True, help_text="% error")
    
    # Rainfall
    predicted_rainfall = models.FloatField(null=True, blank=True, help_text="mm")
    actual_rainfall = models.FloatField(null=True, blank=True, help_text="mm")
    
    # Wind Speed
    predicted_wind_speed = models.FloatField(null=True, blank=True, help_text="km/h")
    actual_wind_speed = models.FloatField(null=True, blank=True, help_text="km/h")
    
    # Pressure
    predicted_pressure = models.FloatField(null=True, blank=True, help_text="mb")
    actual_pressure = models.FloatField(null=True, blank=True, help_text="mb")
    
    # Model metadata
    ensemble_weights = models.JSONField(default=dict, help_text="XGBoost:LSTM:Secondary ratio")
    model_version = models.CharField(max_length=20, default='v3', help_text="v1, v2, or v3")
    
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['location', 'forecast_date']),
            models.Index(fields=['forecast_date', 'day_offset']),
        ]
        ordering = ['-forecast_date', 'day_offset']
    
    def __str__(self):
        return f"{self.location} | {self.forecast_date} (Day +{self.day_offset})"
    
    def save(self, *args, **kwargs):
        """Auto-calculate errors when actual data is provided"""
        if self.actual_temp is not None and self.predicted_temp is not None:
            self.temp_error = self.actual_temp - self.predicted_temp
        if self.actual_humidity is not None and self.predicted_humidity is not None:
            self.humidity_error = abs(self.actual_humidity - self.predicted_humidity)
        super().save(*args, **kwargs)


class FieldEvaluation_WaterQuality(models.Model):
    """Weekly water quality sensor readings vs. lab validation"""
    
    RISK_LEVEL_CHOICES = [
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical'),
    ]
    
    VALIDATION_METHOD_CHOICES = [
        ('lab', 'Lab Analysis'),
        ('expert', 'Expert Assessment'),
        ('sensor', 'Sensor Only'),
    ]
    
    location = models.CharField(max_length=50, db_index=True)
    measurement_date = models.DateField(db_index=True)
    measurement_time = models.TimeField()
    
    # Sensor readings
    sensor_ph = models.FloatField(null=True, blank=True, help_text="Sensor reading")
    sensor_temperature = models.FloatField(null=True, blank=True, help_text="°C")
    sensor_do = models.FloatField(null=True, blank=True, help_text="mg/L (Dissolved Oxygen)")
    sensor_turbidity = models.FloatField(null=True, blank=True, help_text="NTU (Nephelometric Turbidity Units)")
    
    # Lab validation readings
    lab_ph = models.FloatField(null=True, blank=True)
    lab_temperature = models.FloatField(null=True, blank=True, help_text="°C")
    lab_do = models.FloatField(null=True, blank=True, help_text="mg/L")
    lab_turbidity = models.FloatField(null=True, blank=True, help_text="NTU")
    lab_ammonia = models.FloatField(null=True, blank=True, help_text="mg/L")
    lab_nitrite = models.FloatField(null=True, blank=True, help_text="mg/L")
    lab_total_nitrogen = models.FloatField(null=True, blank=True, help_text="mg/L")
    lab_phosphorus = models.FloatField(null=True, blank=True, help_text="mg/L")
    lab_alkalinity = models.FloatField(null=True, blank=True, help_text="mg/L CaCO3")
    
    # Expert/Lab Assessment
    expert_risk_level = models.CharField(max_length=20, choices=RISK_LEVEL_CHOICES, null=True, blank=True)
    actual_survival_rate = models.FloatField(null=True, blank=True, help_text="% shrimp surviving")
    expert_notes = models.TextField(null=True, blank=True)
    
    validation_method = models.CharField(max_length=20, choices=VALIDATION_METHOD_CHOICES, default='sensor')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['location', 'measurement_date']),
        ]
        ordering = ['-measurement_date']
    
    def __str__(self):
        return f"{self.location} | {self.measurement_date}"
    
    @property
    def ph_accuracy(self):
        """Sensor vs lab accuracy for pH"""
        if self.sensor_ph and self.lab_ph:
            return abs(self.sensor_ph - self.lab_ph)
        return None
    
    @property
    def do_accuracy(self):
        """Sensor vs lab accuracy for DO"""
        if self.sensor_do and self.lab_do:
            return abs(self.sensor_do - self.lab_do)
        return None


class FieldEvaluation_FeederEvent(models.Model):
    """Automated feeder dispensing events and performance tracking"""
    
    ERROR_CODE_CHOICES = [
        ('none', 'No Error'),
        ('motor_fail', 'Motor Failure'),
        ('load_cell_error', 'Load Cell Error'),
        ('water_sensor_low', 'Water Level Critical'),
        ('network_timeout', 'Network Timeout'),
        ('config_error', 'Configuration Error'),
    ]
    
    TEST_GROUP_CHOICES = [
        ('control', 'Control Group (Fixed Schedule)'),
        ('test', 'Test Group (ML-Driven)'),
    ]
    
    location = models.CharField(max_length=50, db_index=True)
    event_timestamp = models.DateTimeField(db_index=True)
    
    # Test group assignment
    test_group = models.CharField(max_length=20, choices=TEST_GROUP_CHOICES)
    
    # Dispensing metrics
    planned_amount_grams = models.FloatField()
    actual_dispensed_grams = models.FloatField(null=True, blank=True)
    dispensing_accuracy_percent = models.FloatField(null=True, blank=True)
    feeder_motor_runtime_seconds = models.FloatField(null=True, blank=True)
    
    # System latency
    api_to_feeder_latency_ms = models.IntegerField(null=True, blank=True)
    
    # Feed quality
    shrimp_biomass_estimate_kg = models.FloatField(null=True, blank=True)
    estimated_feed_consumption_percent = models.FloatField(null=True, blank=True, help_text="% of dispensed amount consumed")
    
    # Error tracking
    system_error_code = models.CharField(max_length=50, choices=ERROR_CODE_CHOICES, default='none')
    error_message = models.TextField(null=True, blank=True)
    
    # Post-action metrics
    feed_conversion_ratio = models.FloatField(null=True, blank=True, help_text="kg feed / kg growth")
    shrimp_feeding_response = models.CharField(max_length=50, null=True, blank=True, help_text="Vigorous/Normal/Weak")
    
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['location', 'event_timestamp']),
            models.Index(fields=['test_group', 'event_timestamp']),
        ]
        ordering = ['-event_timestamp']
    
    def __str__(self):
        return f"{self.location} | {self.event_timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate accuracy percentage"""
        if self.actual_dispensed_grams is not None and self.planned_amount_grams > 0:
            self.dispensing_accuracy_percent = (self.actual_dispensed_grams / self.planned_amount_grams) * 100
        super().save(*args, **kwargs)


class FieldEvaluation_SystemMetrics(models.Model):
    """Server performance and system health metrics during field testing"""
    
    measurement_timestamp = models.DateTimeField(db_index=True)
    
    # Availability
    api_uptime_percent = models.FloatField(help_text="% uptime last hour")
    api_latency_ms_p50 = models.IntegerField(null=True, blank=True, help_text="Median latency")
    api_latency_ms_p95 = models.IntegerField(null=True, blank=True, help_text="95th percentile latency")
    api_latency_ms_p99 = models.IntegerField(null=True, blank=True, help_text="99th percentile latency")
    
    # Network
    websocket_latency_ms = models.IntegerField(null=True, blank=True, help_text="Real-time update latency")
    db_query_time_ms = models.IntegerField(null=True, blank=True, help_text="Average DB query duration")
    
    # Server Resources
    cpu_utilization_percent = models.FloatField(null=True, blank=True)
    memory_usage_percent = models.FloatField(null=True, blank=True)
    disk_usage_percent = models.FloatField(null=True, blank=True)
    
    # Sensor Network
    sensor_network_uptime_percent = models.FloatField(null=True, blank=True)
    sensors_reporting = models.IntegerField(default=0, help_text="Count of active sensors")
    
    # Usage
    concurrent_users_count = models.IntegerField(default=0)
    api_requests_last_hour = models.IntegerField(default=0)
    
    # Errors
    errors_count_last_1h = models.IntegerField(default=0)
    warnings_count_last_1h = models.IntegerField(default=0)
    critical_errors = models.TextField(null=True, blank=True, help_text="List of critical issues")
    
    # Model Inference
    weather_forecast_generation_ms = models.IntegerField(null=True, blank=True)
    water_quality_prediction_ms = models.IntegerField(null=True, blank=True)
    feeder_recommendation_ms = models.IntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['measurement_timestamp']),
        ]
        ordering = ['-measurement_timestamp']
    
    def __str__(self):
        return f"Metrics @ {self.measurement_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


class FieldEvaluation_FieldLog(models.Model):
    """Daily observer logs from the field"""
    
    CLARITY_CHOICES = [
        ('clear', 'Clear'),
        ('turbid', 'Turbid'),
        ('opaque', 'Opaque'),
    ]
    
    FEEDING_RESPONSE_CHOICES = [
        ('vigorous', 'Vigorous'),
        ('normal', 'Normal'),
        ('weak', 'Weak'),
    ]
    
    RESIDUAL_CHOICES = [
        ('minimal', 'Minimal'),
        ('moderate', 'Moderate'),
        ('excessive', 'Excessive'),
    ]
    
    location = models.CharField(max_length=50, db_index=True)
    log_date = models.DateField(db_index=True)
    observer_name = models.CharField(max_length=100)
    
    # Weather observations
    temp_min_celsius = models.FloatField(null=True, blank=True)
    temp_max_celsius = models.FloatField(null=True, blank=True)
    rainfall_mm = models.FloatField(null=True, blank=True)
    wind_speed_kmh = models.FloatField(null=True, blank=True)
    wind_direction = models.CharField(max_length=20, null=True, blank=True)
    weather_notes = models.TextField(null=True, blank=True)
    
    # Water quality observations
    water_clarity = models.CharField(max_length=20, choices=CLARITY_CHOICES, null=True, blank=True)
    water_color = models.CharField(max_length=50, null=True, blank=True)
    water_odor_normal = models.BooleanField(default=True)
    odor_description = models.CharField(max_length=100, null=True, blank=True)
    
    # Shrimp behavior
    shrimp_feeding_response = models.CharField(max_length=20, choices=FEEDING_RESPONSE_CHOICES, null=True, blank=True)
    observed_behavior = models.TextField(null=True, blank=True)
    
    # Feeder observations
    feed_residual = models.CharField(max_length=20, choices=RESIDUAL_CHOICES, null=True, blank=True)
    feeder_errors_observed = models.BooleanField(default=False)
    feeder_error_description = models.TextField(null=True, blank=True)
    
    # Maintenance
    sensors_cleaned = models.BooleanField(default=False)
    calibration_check_passed = models.BooleanField(default=True)
    maintenance_notes = models.TextField(null=True, blank=True)
    
    # General notes
    general_notes = models.TextField(null=True, blank=True)
    photo_paths = models.JSONField(default=list, help_text="List of relative paths to field photos")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['location', 'log_date']),
        ]
        ordering = ['-log_date']
    
    def __str__(self):
        return f"{self.location} | {self.log_date} | Observer: {self.observer_name}"


# ============================================================================
# EVALUATION ANALYSIS FUNCTIONS
# ============================================================================

class EvaluationAnalyzer:
    """Computes summary statistics and accuracy metrics from field evaluation data"""
    
    @staticmethod
    def weather_forecast_metrics(location=None, days_ago=7):
        """
        Calculate weather forecast accuracy metrics for the past N days
        Returns: {temperature: {mae, rmse, mbe}, humidity: {...}, ...}
        """
        from django.db.models import Q, Avg, StdDev
        from django.db.models.functions import Cast
        from django.db import models as django_models
        
        cutoff_date = timezone.now().date() - timedelta(days=days_ago)
        query = FieldEvaluation_WeatherForecast.objects.filter(
            forecast_date__gte=cutoff_date,
            actual_temp__isnull=False,
            predicted_temp__isnull=False
        )
        
        if location:
            query = query.filter(location=location)
        
        forecasts = list(query)
        if not forecasts:
            return {}
        
        def safe_mean_abs_error(param_name):
            values = [(f.predicted_temp, f.actual_temp) for f in forecasts]
            if not values:
                return None
            errors = [abs(p - a) for p, a in values if p and a]
            return sum(errors) / len(errors) if errors else None
        
        # Temperature metrics
        temp_errors = [f.temp_error for f in forecasts if f.temp_error is not None]
        
        metrics = {
            'period_days': days_ago,
            'forecast_count': len(forecasts),
            'temperature': {
                'mae': sum(abs(e) for e in temp_errors) / len(temp_errors) if temp_errors else None,
                'mbe': sum(temp_errors) / len(temp_errors) if temp_errors else None,  # bias
                'rmse': (sum(e**2 for e in temp_errors) / len(temp_errors))**0.5 if temp_errors else None,
            },
            'by_day_offset': {}
        }
        
        # Breakdown by day offset
        for day in range(1, 8):
            day_forecasts = [f for f in forecasts if f.day_offset == day]
            if day_forecasts:
                errors = [f.temp_error for f in day_forecasts if f.temp_error is not None]
                if errors:
                    metrics['by_day_offset'][f'day_{day}'] = {
                        'count': len(errors),
                        'mae': sum(abs(e) for e in errors) / len(errors),
                        'mbe': sum(errors) / len(errors),
                    }
        
        return metrics
    
    @staticmethod
    def water_quality_validation_metrics(location=None, days_ago=30):
        """Summarize sensor vs lab validation metrics for water quality."""

        cutoff_date = timezone.now().date() - timedelta(days=days_ago)
        query = FieldEvaluation_WaterQuality.objects.filter(
            measurement_date__gte=cutoff_date,
            validation_method='lab'
        )

        if location:
            query = query.filter(location=location)

        measurements = list(query)
        if not measurements:
            return {}

        ph_diffs = [m.ph_accuracy for m in measurements if m.ph_accuracy is not None]
        do_diffs = [m.do_accuracy for m in measurements if m.do_accuracy is not None]

        metrics = {
            'period_days': days_ago,
            'measurement_count': len(measurements),
            'sensor_accuracy': {},
        }

        if ph_diffs:
            metrics['sensor_accuracy']['ph'] = {
                'mean_error': sum(ph_diffs) / len(ph_diffs),
                'max_error': max(ph_diffs),
            }

        if do_diffs:
            metrics['sensor_accuracy']['do'] = {
                'mean_error': sum(do_diffs) / len(do_diffs),
                'max_error': max(do_diffs),
            }

        return metrics
    
    @staticmethod
    def feeder_performance_summary(location=None, days_ago=30, test_group=None):
        """
        Aggregate feeder dispensing accuracy and feed efficiency metrics
        Returns: {dispensing_accuracy, uptime, fcr, error_rate}
        """
        cutoff_date = timezone.now().date() - timedelta(days=days_ago)
        query = FieldEvaluation_FeederEvent.objects.filter(
            event_timestamp__gte=cutoff_date
        )
        
        if location:
            query = query.filter(location=location)
        
        if test_group:
            query = query.filter(test_group=test_group)
        
        events = list(query)
        if not events:
            return {}
        
        # Dispensing accuracy
        accuracy_values = [e.dispensing_accuracy_percent for e in events if e.dispensing_accuracy_percent is not None]
        
        # Error rate
        errors = [e for e in events if e.system_error_code != 'none']
        
        # FCR (only for completed events)
        fcr_values = [e.feed_conversion_ratio for e in events if e.feed_conversion_ratio is not None]
        
        metrics = {
            'period_days': days_ago,
            'total_feeding_events': len(events),
            'dispensing': {
                'accuracy_percent_mean': sum(accuracy_values) / len(accuracy_values) if accuracy_values else None,
                'accuracy_percent_std': (
                    sum((x - (sum(accuracy_values)/len(accuracy_values)))**2 for x in accuracy_values) / len(accuracy_values)
                )**0.5 if accuracy_values else None,
                'within_5_percent': sum(1 for a in accuracy_values if 95 <= a <= 105) / len(accuracy_values) if accuracy_values else None,
            },
            'reliability': {
                'error_free_percent': (1 - len(errors) / len(events)) * 100 if events else 100,
                'total_errors': len(errors),
                'mttr_minutes': None,  # Mean Time To Recovery - needs manual follow-up
            },
            'feed_efficiency': {
                'fcr_mean': sum(fcr_values) / len(fcr_values) if fcr_values else None,
                'fcr_count': len(fcr_values),
            },
        }
        
        return metrics
    
    @staticmethod
    def system_health_summary(days_ago=7):
        """
        Overall system availability, latency, and resource utilization
        """
        cutoff_date = timezone.now() - timedelta(days=days_ago)
        metrics = FieldEvaluation_SystemMetrics.objects.filter(
            measurement_timestamp__gte=cutoff_date
        ).order_by('-measurement_timestamp')
        
        if not metrics.exists():
            return {}
        
        uptime_values = [m.api_uptime_percent for m in metrics if m.api_uptime_percent is not None]
        latency_p95 = [m.api_latency_ms_p95 for m in metrics if m.api_latency_ms_p95 is not None]
        cpu_values = [m.cpu_utilization_percent for m in metrics if m.cpu_utilization_percent is not None]
        
        summary = {
            'period_days': days_ago,
            'measurement_count': metrics.count(),
            'api_uptime': {
                'mean_percent': sum(uptime_values) / len(uptime_values) if uptime_values else None,
                'min_percent': min(uptime_values) if uptime_values else None,
            },
            'latency_p95': {
                'mean_ms': sum(latency_p95) / len(latency_p95) if latency_p95 else None,
                'max_ms': max(latency_p95) if latency_p95 else None,
            },
            'cpu_utilization': {
                'mean_percent': sum(cpu_values) / len(cpu_values) if cpu_values else None,
                'max_percent': max(cpu_values) if cpu_values else None,
            },
        }
        
        return summary


# ============================================================================
# MANAGEMENT COMMAND FOR FIELD DATA IMPORT
# ============================================================================

class FieldEvaluationManager:
    """Helper class to import field data from CSV/JSON monitoring logs"""
    
    @staticmethod
    def import_weather_forecast_csv(csv_file_path):
        """Import weather forecast data from CSV"""
        import csv
        import pandas as pd
        
        df = pd.read_csv(csv_file_path)
        created = 0
        
        for _, row in df.iterrows():
            obj, created_flag = FieldEvaluation_WeatherForecast.objects.update_or_create(
                location=row['location'],
                forecast_date=pd.to_datetime(row['forecast_date']).date(),
                day_offset=int(row['day_offset']),
                defaults={
                    'predicted_temp': float(row['predicted_temp']) if pd.notna(row['predicted_temp']) else None,
                    'actual_temp': float(row['actual_temp']) if pd.notna(row['actual_temp']) else None,
                    'predicted_humidity': float(row['predicted_humidity']) if pd.notna(row['predicted_humidity']) else None,
                    'actual_humidity': float(row['actual_humidity']) if pd.notna(row['actual_humidity']) else None,
                    'forecast_issued_at': timezone.now(),
                }
            )
            if created_flag:
                created += 1
        
        return {'created': created}
    
    @staticmethod
    def export_metrics_report(output_path, start_date, end_date, locations=None):
        """Generate comprehensive metrics CSV report"""
        import csv
        
        weather_metrics = FieldEvaluation_WeatherForecast.objects.filter(
            forecast_date__gte=start_date,
            forecast_date__lte=end_date
        )
        
        if locations:
            weather_metrics = weather_metrics.filter(location__in=locations)
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'location', 'forecast_date', 'day_offset', 'predicted_temp', 'actual_temp', 'temp_error',
                'predicted_humidity', 'actual_humidity', 'humidity_error'
            ])
            writer.writeheader()
            
            for metric in weather_metrics:
                writer.writerow({
                    'location': metric.location,
                    'forecast_date': metric.forecast_date,
                    'day_offset': metric.day_offset,
                    'predicted_temp': metric.predicted_temp,
                    'actual_temp': metric.actual_temp,
                    'temp_error': metric.temp_error,
                    'predicted_humidity': metric.predicted_humidity,
                    'actual_humidity': metric.actual_humidity,
                    'humidity_error': metric.humidity_error,
                })
        
        return output_path

