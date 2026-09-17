from django.db import models
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import datetime
import json

class SensorReading(models.Model):
    # null = sensor disconnected / no reading (do not store 0 for missing)
    temperature = models.FloatField(null=True, blank=True)
    ph = models.FloatField(null=True, blank=True)
    turbidity = models.FloatField(null=True, blank=True)
    tds = models.IntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Sensor reading at {self.timestamp}"

class Threshold(models.Model):
    PARAMETER_CHOICES = [
        ('temperature', 'Temperature'),
        ('ph', 'pH'),
        ('turbidity', 'Turbidity'),
        ('tds', 'TDS'),
    ]

    parameter = models.CharField(max_length=20, choices=PARAMETER_CHOICES, unique=True)
    min_value = models.FloatField()
    max_value = models.FloatField()
    unit = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return f"{self.parameter} threshold: {self.min_value}-{self.max_value} {self.unit}"


class SensorCalibration(models.Model):
    """Website adjustment: display = (raw * scale) + offset (no Arduino re-upload)."""
    PARAMETER_CHOICES = Threshold.PARAMETER_CHOICES

    parameter = models.CharField(max_length=20, choices=PARAMETER_CHOICES, unique=True)
    scale = models.FloatField(default=1.0)
    offset = models.FloatField(default=0.0)
    unit = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return f"{self.parameter} cal: x{self.scale} + {self.offset}"

class Alert(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('warning', 'Warning'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    parameter = models.CharField(max_length=20)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    # null value = disconnected / no reading (not a numeric threshold breach)
    value = models.FloatField(null=True, blank=True)
    threshold_min = models.FloatField(null=True, blank=True, default=0)
    threshold_max = models.FloatField(null=True, blank=True, default=0)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    email_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.severity} {self.parameter} alert: {self.value}"

class WeatherCache(models.Model):
    city = models.CharField(max_length=100)
    data = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['city']
        ordering = ['-timestamp']

    @staticmethod
    def get_weather(city):
        cache_key = f"weather_{city.lower().replace(' ', '_')}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            weather_obj = WeatherCache.objects.get(city__iexact=city)
            # Check if cache is still valid (10 minutes)
            from django.utils import timezone
            if (timezone.now() - weather_obj.timestamp).total_seconds() < 600:
                cache.set(cache_key, weather_obj.data, 600)
                return weather_obj.data
            else:
                weather_obj.delete()  # Expired
        except WeatherCache.DoesNotExist:
            pass
        return None

    @staticmethod
    def set_weather(city, data):
        WeatherCache.objects.update_or_create(
            city__iexact=city,
            defaults={'data': data, 'city': city}
        )
        cache_key = f"weather_{city.lower().replace(' ', '_')}"
        cache.set(cache_key, data, 600)

class WeatherForecast(models.Model):
    """Store weather forecast data from CSV dataset"""
    FORECAST_TYPE_CHOICES = [
        ('current', 'Current Weather'),
        ('tomorrow', 'Tomorrow Forecast'),
        ('daily', 'Daily Forecast'),
    ]
    
    # Location information
    city = models.CharField(max_length=100, db_index=True)
    municipality = models.CharField(max_length=100, blank=True, db_index=True, help_text="Municipality or district")
    province = models.CharField(max_length=100, blank=True, db_index=True, help_text="Province, state, or region")
    country = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    # Forecast details
    forecast_type = models.CharField(max_length=20, choices=FORECAST_TYPE_CHOICES, default='current')
    forecast_date = models.DateField(db_index=True)  # The date this forecast is for
    
    # Weather conditions
    temperature = models.FloatField(help_text="Temperature in Celsius")
    feels_like = models.FloatField(null=True, blank=True, help_text="Feels like temperature")
    min_temperature = models.FloatField(null=True, blank=True)
    max_temperature = models.FloatField(null=True, blank=True)
    condition = models.CharField(max_length=100, help_text="Weather condition description")
    
    # Atmospheric data
    humidity = models.IntegerField(help_text="Humidity percentage")
    pressure = models.FloatField(help_text="Atmospheric pressure in hPa")
    cloud_cover = models.IntegerField(default=0, help_text="Cloud coverage percentage")
    
    # Wind data
    wind_speed = models.FloatField(help_text="Wind speed in km/h")
    wind_direction = models.CharField(max_length=10, blank=True)
    wind_degree = models.IntegerField(null=True, blank=True)
    gust_speed = models.FloatField(null=True, blank=True)
    
    # Precipitation
    precipitation = models.FloatField(default=0.0, help_text="Precipitation in mm")
    
    # Visibility and UV
    visibility = models.FloatField(null=True, blank=True, help_text="Visibility in km")
    uv_index = models.IntegerField(default=0)
    
    # Astronomical data
    sunrise = models.CharField(max_length=20, blank=True)
    sunset = models.CharField(max_length=20, blank=True)
    moon_phase = models.CharField(max_length=50, blank=True)
    moon_illumination = models.IntegerField(null=True, blank=True)
    
    # Icon for display
    weather_icon = models.CharField(max_length=10, blank=True, help_text="Weather icon code")
    
    # Shrimp farming impact
    temperature_impact = models.CharField(max_length=20, blank=True, choices=[
        ('optimal', 'Optimal'),
        ('normal', 'Normal'),
        ('moderate_risk', 'Moderate Risk'),
        ('high_risk', 'High Risk'),
    ])
    rain_impact = models.CharField(max_length=20, blank=True, choices=[
        ('normal', 'Normal'),
        ('moderate_risk', 'Moderate Risk'),
        ('high_risk', 'High Risk'),
    ])
    wind_impact = models.CharField(max_length=20, blank=True, choices=[
        ('optimal', 'Optimal'),
        ('normal', 'Normal'),
        ('moderate_risk', 'Moderate Risk'),
        ('high_risk', 'High Risk'),
    ])
    
    # Recommendations (JSON array)
    recommendations = models.JSONField(default=list, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    source = models.CharField(max_length=50, default='csv_dataset', help_text="Data source")
    
    class Meta:
        ordering = ['forecast_date', 'country', 'province', 'municipality', 'city']
        indexes = [
            models.Index(fields=['city', 'forecast_date']),
            models.Index(fields=['province', 'forecast_date']),
            models.Index(fields=['municipality', 'forecast_date']),
            models.Index(fields=['country', 'forecast_date']),
            models.Index(fields=['forecast_type', 'forecast_date']),
            models.Index(fields=['-created_at']),
        ]
        unique_together = ['city', 'province', 'municipality', 'forecast_date', 'forecast_type']
    
    def __str__(self):
        location = self.city
        if self.municipality:
            location = f"{self.municipality}, {location}"
        if self.province:
            location = f"{self.province}, {location}"
        if self.country:
            location = f"{location}, {self.country}"
        return f"{location} - {self.get_forecast_type_display()} for {self.forecast_date}: {self.temperature}°C, {self.condition}"
    
    def calculate_impacts(self):
        """Calculate and update impact assessments for shrimp farming"""
        # Temperature impact
        if self.temperature > 32:
            self.temperature_impact = 'high_risk'
        elif self.temperature > 28:
            self.temperature_impact = 'moderate_risk'
        elif 24 <= self.temperature <= 27:
            self.temperature_impact = 'optimal'
        elif self.temperature < 20:
            self.temperature_impact = 'moderate_risk'
        else:
            self.temperature_impact = 'normal'
        
        # Rain impact
        if self.precipitation > 20:
            self.rain_impact = 'high_risk'
        elif self.precipitation > 5:
            self.rain_impact = 'moderate_risk'
        else:
            self.rain_impact = 'normal'
        
        # Wind impact
        if self.wind_speed > 40:
            self.wind_impact = 'high_risk'
        elif self.wind_speed > 25:
            self.wind_impact = 'moderate_risk'
        elif 10 <= self.wind_speed <= 25:
            self.wind_impact = 'optimal'
        else:
            self.wind_impact = 'normal'
        
        # Generate recommendations
        recs = []
        
        if self.temperature_impact == 'high_risk':
            recs.append('⚠️ High temperature alert: Increase aeration, monitor oxygen levels closely')
        elif self.temperature_impact == 'moderate_risk':
            if self.temperature > 28:
                recs.append('Elevated temperature: Ensure adequate water circulation')
            else:
                recs.append('Low temperature: Reduce feeding, shrimp metabolism is slower')
        
        if self.rain_impact == 'high_risk':
            recs.append('🌧️ Heavy rain expected: Monitor salinity and pH, reduce feeding')
        elif self.rain_impact == 'moderate_risk':
            recs.append('Moderate rain: Check water quality after rainfall')
        
        if self.wind_impact == 'high_risk':
            recs.append('💨 Strong winds: Secure equipment, monitor water turbidity')
        elif self.wind_impact == 'optimal':
            recs.append('✅ Good wind conditions for natural aeration')
        
        if self.uv_index > 8:
            recs.append('High UV index: Consider shade nets to reduce heat stress')
        
        if not recs:
            recs.append('✅ Weather conditions are favorable for shrimp farming')
        
        self.recommendations = recs
        return recs

class Feeder(models.Model):
    # Basic settings
    auto_enabled = models.BooleanField(default=False)
    interval_minutes = models.IntegerField(default=60)  # For simple interval-based feeding
    portion_grams = models.IntegerField(default=50)
    capacity_max = models.IntegerField(default=1000)
    capacity_current = models.IntegerField(default=1000)
    low_percent = models.IntegerField(default=15)
    next_feed_at = models.DateTimeField(null=True, blank=True)
    last_fed_at = models.DateTimeField(null=True, blank=True)

    # Advanced scheduling
    SCHEDULE_CHOICES = [
        ('interval', 'Interval-based'),
        ('daily', 'Daily schedule'),
        ('adaptive', 'Weather-adaptive'),
    ]
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_CHOICES, default='interval')

    # Daily schedule (JSON array of times, e.g., ["08:00", "14:00", "20:00"])
    daily_schedule = models.JSONField(default=list, blank=True)

    # Applied ML plan for a calendar day (shown when opening Feeding page)
    # Example: {"date":"2026-07-27","total_kg":6.37,"slots_kg":{"06:00":0.95,...},"doc":2,...}
    today_feed_plan = models.JSONField(null=True, blank=True)

    # Weather adaptation settings
    weather_adaptation = models.BooleanField(default=False)
    rain_reduction_percent = models.IntegerField(default=20)  # Reduce feeding by % in rain
    heat_increase_percent = models.IntegerField(default=10)   # Increase feeding by % in heat
    extreme_weather_pause = models.BooleanField(default=True) # Pause feeding in extreme conditions

    # Smart optimization
    smart_optimization = models.BooleanField(default=False)
    behavior_adjustment = models.BooleanField(default=True)   # Adjust based on shrimp behavior
    water_quality_adjustment = models.BooleanField(default=True) # Adjust based on water conditions

    # Alert settings
    alerts_enabled = models.BooleanField(default=True)
    missed_feed_alert = models.BooleanField(default=True)
    low_feed_alert = models.BooleanField(default=True)
    weather_alert = models.BooleanField(default=False)

    class Meta:
        ordering = ['-last_fed_at']

    def __str__(self):
        return f"Feeder: {self.capacity_current}/{self.capacity_max}g, mode={self.schedule_type}, auto={self.auto_enabled}"

    def get_next_feed_time(self):
        """Calculate next feeding time based on schedule type"""
        from django.utils import timezone
        now = timezone.now()

        if self.schedule_type == 'interval':
            if self.next_feed_at and self.next_feed_at > now:
                return self.next_feed_at
            return now + timezone.timedelta(minutes=self.interval_minutes)

        elif self.schedule_type == 'daily':
            if not self.daily_schedule:
                return now + timezone.timedelta(hours=1)  # Default fallback

            today = now.date()
            current_time = now.time()

            # Find next feeding time today
            for time_str in sorted(self.daily_schedule):
                feed_time = timezone.datetime.strptime(time_str, '%H:%M').time()
                if feed_time > current_time:
                    next_feed = timezone.datetime.combine(today, feed_time)
                    next_feed = timezone.make_aware(next_feed)
                    return next_feed

            # No more feeds today, schedule first feed tomorrow
            if self.daily_schedule:
                first_time = timezone.datetime.strptime(sorted(self.daily_schedule)[0], '%H:%M').time()
                tomorrow = today + timezone.timedelta(days=1)
                next_feed = timezone.datetime.combine(tomorrow, first_time)
                next_feed = timezone.make_aware(next_feed)
                return next_feed

        return now + timezone.timedelta(hours=1)  # Default fallback

    def should_feed_based_on_weather(self, weather_data):
        """Determine if feeding should proceed based on weather conditions"""
        if not self.weather_adaptation or not weather_data:
            return True

        # Check for extreme weather
        if self.extreme_weather_pause:
            # Pause feeding in extreme conditions (customize thresholds as needed)
            temp = weather_data.get('temperature', 25)
            if temp > 35 or temp < 15:  # Extreme heat/cold
                return False

            description = weather_data.get('description', '').lower()
            if 'storm' in description or 'hurricane' in description:
                return False

        return True

    def adjust_portion_for_weather(self, base_portion, weather_data):
        """Adjust feeding portion based on weather"""
        if not self.weather_adaptation or not weather_data:
            return base_portion

        adjustment = 0
        description = weather_data.get('description', '').lower()

        # Rain reduction
        if 'rain' in description and self.rain_reduction_percent > 0:
            adjustment -= self.rain_reduction_percent

        # Heat increase
        temp = weather_data.get('temperature', 25)
        if temp > 30 and self.heat_increase_percent > 0:
            adjustment += self.heat_increase_percent

        adjusted_portion = base_portion * (1 + adjustment / 100)
        return max(10, min(adjusted_portion, self.capacity_max))  # Reasonable bounds

    def adjust_portion_for_shrimp_size(self, base_portion, avg_shrimp_weight_grams):
        """Adjust feeding portion based on average shrimp size"""
        # Smaller shrimp need less food, larger shrimp need more
        # Base 1.0 multiplier at 5 grams
        if avg_shrimp_weight_grams <= 0:
            return base_portion
        
        # Use a growth curve: multiplier increases with size
        # At 1g: 0.5x, at 5g: 1.0x, at 15g: 1.5x
        if avg_shrimp_weight_grams < 5:
            multiplier = 0.5 + (avg_shrimp_weight_grams / 5) * 0.5
        else:
            multiplier = 1.0 + ((avg_shrimp_weight_grams - 5) / 10) * 0.5
        
        adjusted = base_portion * multiplier
        return max(10, min(adjusted, self.capacity_max))

    def get_recommended_feed_type(self, avg_shrimp_weight_grams):
        """Get the best feed type for current shrimp size"""
        from django.db.models import Q
        
        try:
            feed = FeedType.objects.filter(
                is_active=True,
                target_min_weight_grams__lte=avg_shrimp_weight_grams,
                target_max_weight_grams__gte=avg_shrimp_weight_grams,
            ).first()
            
            if feed:
                return feed
            
            # If no exact match, find closest
            if avg_shrimp_weight_grams < 1:
                return FeedType.objects.filter(is_active=True, category='starter').first()
            elif avg_shrimp_weight_grams < 3:
                return FeedType.objects.filter(is_active=True, category='juvenile').first()
            else:
                return FeedType.objects.filter(is_active=True, category='grower').first()
        except FeedType.DoesNotExist:
            return None


class FeedType(models.Model):
    """Different feed types for different shrimp sizes and conditions."""
    FEED_CATEGORY_CHOICES = [
        ('starter', 'Starter Feed (PL5-PL10)'),
        ('nursery', 'Nursery Feed (PL10-0.5g)'),
        ('juvenile', 'Juvenile Feed (0.5g-3g)'),
        ('grower', 'Grower Feed (3g-8g)'),
        ('finisher', 'Finisher Feed (8g+)'),
        ('specialty', 'Specialty Feed'),
    ]
    
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=FEED_CATEGORY_CHOICES, default='grower')
    protein_percent = models.FloatField(help_text='Protein content percentage')
    fat_percent = models.FloatField(help_text='Fat content percentage')
    fiber_percent = models.FloatField(help_text='Fiber content percentage')
    size_microns = models.IntegerField(help_text='Feed pellet size in microns')
    target_min_weight_grams = models.FloatField(help_text='Minimum shrimp weight for this feed')
    target_max_weight_grams = models.FloatField(help_text='Maximum shrimp weight for this feed')
    cost_per_kg = models.FloatField(default=0.0, help_text='Cost per kilogram')
    manufacturer = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['target_min_weight_grams']
        verbose_name_plural = "Feed Types"

    def __str__(self):
        return f"{self.name} ({self.category}) - {self.target_min_weight_grams}g-{self.target_max_weight_grams}g"


class FeedingLog(models.Model):
    feeder = models.ForeignKey(Feeder, on_delete=models.CASCADE, related_name='feeding_logs')
    feed_product = models.ForeignKey(FeedType, on_delete=models.SET_NULL, null=True, blank=True, related_name='feeding_logs', help_text='Specific feed product used')
    timestamp = models.DateTimeField(auto_now_add=True)
    feed_type = models.CharField(max_length=20, choices=[
        ('scheduled', 'Scheduled Auto Feed'),
        ('manual', 'Manual Feed'),
        ('weather_adjusted', 'Weather-Adjusted Feed'),
        ('smart_adjusted', 'Smart-Adjusted Feed'),
    ], default='scheduled')
    portion_grams = models.IntegerField()
    capacity_before = models.IntegerField()
    capacity_after = models.IntegerField()
    weather_conditions = models.JSONField(null=True, blank=True)  # Weather at time of feeding
    shrimp_size_adjustment_factor = models.FloatField(default=1.0, help_text='Multiplier based on average shrimp size')
    notes = models.TextField(blank=True)  # Any special notes or adjustments

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Feed at {self.timestamp}: {self.portion_grams}g ({self.feed_type})"


class FeederTelemetry(models.Model):
    """Lightweight telemetry from feeder hardware (motor state + ultrasonic distance)."""

    timestamp = models.DateTimeField(auto_now_add=True)
    motor_state = models.CharField(max_length=10, blank=True, default='')
    distance_cm = models.FloatField(null=True, blank=True)
    device_id = models.CharField(max_length=64, blank=True, default='')
    run_started_at = models.DateTimeField(null=True, blank=True)
    run_stopped_at = models.DateTimeField(null=True, blank=True)
    run_seconds = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Feeder telemetry at {self.timestamp}"

class Report(models.Model):
    REPORT_TYPE_CHOICES = [
        ('daily', 'Daily Report'),
        ('weekly', 'Weekly Report'),
        ('monthly', 'Monthly Report'),
        ('custom', 'Custom Report'),
        ('seasonal', 'Seasonal Report'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    # Report metadata
    title = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, default='daily')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Date range for the report
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    # Report data (JSON format for flexibility)
    data = models.JSONField(default=dict, blank=True)
    
    # Summary statistics
    summary = models.JSONField(default=dict, blank=True)  # Key metrics, averages, totals
    
    # Insights and recommendations
    insights = models.JSONField(default=list, blank=True)  # AI-generated or rule-based insights
    recommendations = models.JSONField(default=list, blank=True)  # Actionable recommendations
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    generated_at = models.DateTimeField(null=True, blank=True)  # When report generation completed
    
    # File attachment (if exported as PDF/Excel)
    file_path = models.CharField(max_length=500, blank=True)
    file_format = models.CharField(max_length=20, blank=True)  # pdf, excel, csv
    
    # User notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['report_type', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __str__(self):
        return f"{self.get_report_type_display()} - {self.title} ({self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')})"
    
    def generate_summary(self):
        """Generate summary statistics for the report period"""
        from django.db.models import Avg, Max, Min, Count
        
        # Get sensor data for the period
        sensor_readings = SensorReading.objects.filter(
            timestamp__gte=self.start_date,
            timestamp__lte=self.end_date
        )
        
        sensor_stats = sensor_readings.aggregate(
            avg_temperature=Avg('temperature'),
            max_temperature=Max('temperature'),
            min_temperature=Min('temperature'),
            avg_ph=Avg('ph'),
            max_ph=Max('ph'),
            min_ph=Min('ph'),
            avg_oxygen=Avg('oxygen'),
            max_oxygen=Max('oxygen'),
            min_oxygen=Min('oxygen'),
            avg_tds=Avg('tds'),
            max_tds=Max('tds'),
            min_tds=Min('tds'),
            total_readings=Count('id')
        )
        
        # Get alert data for the period
        alerts = Alert.objects.filter(
            timestamp__gte=self.start_date,
            timestamp__lte=self.end_date
        )
        
        alert_stats = {
            'total_alerts': alerts.count(),
            'high_severity': alerts.filter(severity='high').count(),
            'low_severity': alerts.filter(severity='low').count(),
            'resolved_alerts': alerts.filter(resolved=True).count(),
            'alerts_by_parameter': {}
        }
        
        for param in ['temperature', 'ph', 'oxygen', 'tds']:
            alert_stats['alerts_by_parameter'][param] = alerts.filter(parameter=param).count()
        
        # Get feeding data for the period
        feeding_logs = FeedingLog.objects.filter(
            timestamp__gte=self.start_date,
            timestamp__lte=self.end_date
        )
        
        feeding_stats = {
            'total_feeds': feeding_logs.count(),
            'total_feed_amount': sum([log.portion_grams for log in feeding_logs]),
            'manual_feeds': feeding_logs.filter(feed_type='manual').count(),
            'scheduled_feeds': feeding_logs.filter(feed_type='scheduled').count(),
            'weather_adjusted_feeds': feeding_logs.filter(feed_type='weather_adjusted').count(),
            'smart_adjusted_feeds': feeding_logs.filter(feed_type='smart_adjusted').count(),
        }
        
        # Compile summary
        self.summary = {
            'sensors': sensor_stats,
            'alerts': alert_stats,
            'feeding': feeding_stats,
            'period': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat(),
                'duration_days': (self.end_date - self.start_date).days
            }
        }
        
        return self.summary
    
    def generate_insights(self):
        """Generate insights based on the data"""
        insights = []
        
        if not self.summary:
            self.generate_summary()
        
        sensor_stats = self.summary.get('sensors', {})
        alert_stats = self.summary.get('alerts', {})
        feeding_stats = self.summary.get('feeding', {})
        
        # Temperature insights
        avg_temp = sensor_stats.get('avg_temperature', 0)
        if avg_temp:
            if avg_temp < 26:
                insights.append({
                    'type': 'warning',
                    'category': 'temperature',
                    'message': f'Average temperature ({avg_temp:.1f}°C) is below optimal range (28-30°C)',
                    'recommendation': 'Consider increasing water temperature for better shrimp growth'
                })
            elif avg_temp > 32:
                insights.append({
                    'type': 'warning',
                    'category': 'temperature',
                    'message': f'Average temperature ({avg_temp:.1f}°C) is above optimal range (28-30°C)',
                    'recommendation': 'Implement cooling measures to reduce temperature stress'
                })
            else:
                insights.append({
                    'type': 'success',
                    'category': 'temperature',
                    'message': f'Temperature is well maintained at {avg_temp:.1f}°C',
                    'recommendation': 'Continue current temperature management'
                })
        
        # pH insights
        avg_ph = sensor_stats.get('avg_ph', 0)
        if avg_ph:
            if avg_ph < 7.5 or avg_ph > 8.5:
                insights.append({
                    'type': 'warning',
                    'category': 'ph',
                    'message': f'pH level ({avg_ph:.1f}) is outside optimal range (7.5-8.5)',
                    'recommendation': 'Adjust water pH to prevent stress on shrimp'
                })
        
        # Oxygen insights
        avg_oxygen = sensor_stats.get('avg_oxygen', 0)
        if avg_oxygen and avg_oxygen < 5:
            insights.append({
                'type': 'critical',
                'category': 'oxygen',
                'message': f'Low dissolved oxygen levels ({avg_oxygen:.1f} mg/L)',
                'recommendation': 'Increase aeration immediately to prevent mortality'
            })
        
        # Alert insights
        total_alerts = alert_stats.get('total_alerts', 0)
        if total_alerts > 10:
            insights.append({
                'type': 'warning',
                'category': 'alerts',
                'message': f'High number of alerts ({total_alerts}) during this period',
                'recommendation': 'Review and address underlying water quality issues'
            })
        
        # Feeding insights
        total_feeds = feeding_stats.get('total_feeds', 0)
        if total_feeds < 1:
            insights.append({
                'type': 'warning',
                'category': 'feeding',
                'message': 'No feeding records during this period',
                'recommendation': 'Ensure feeding schedule is properly configured'
            })
        
        self.insights = insights
        return insights


# ── Season / Harvest Management ───────────────────────────────────────

class Season(models.Model):
    """Represents a grow-out / harvest cycle."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seasons')
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    total_harvest_kg = models.FloatField(default=0.0)
    harvest_count = models.IntegerField(default=0)
    entry_count = models.IntegerField(default=0)
    stocking_density = models.IntegerField(default=0, help_text='Stocking density (shrimp per m²)')
    initial_shrimp_quantity = models.IntegerField(
        default=0,
        help_text='Shrimp pieces stocked at the start of the season',
    )
    current_shrimp_quantity = models.IntegerField(default=0, help_text='Current estimated shrimp count in pond')
    average_shrimp_weight_grams = models.FloatField(default=0.0, help_text='Average shrimp weight in grams')
    notes = models.TextField(default='', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'name'],
                name='unique_season_name_per_user',
            ),
        ]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.start_date})"

    def recompute_totals(self):
        """Recalculate totals from related HarvestEntry records."""
        agg = self.entries.aggregate(
            total_kg=Sum('amount'),
            count=Count('id'),
        )
        harvest_agg = self.entries.filter(amount__gt=0).aggregate(
            h_count=Count('id'),
        )
        self.total_harvest_kg = agg['total_kg'] or 0.0
        self.entry_count = agg['count'] or 0
        self.harvest_count = harvest_agg['h_count'] or 0
        self.save(update_fields=['total_harvest_kg', 'entry_count', 'harvest_count', 'updated_at'])


class HarvestEntry(models.Model):
    """A single harvest event within a season."""
    UNIT_CHOICES = [
        ('kg', 'Kilograms'),
        ('tonnes', 'Tonnes'),
        ('pieces', 'Pieces'),
    ]
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='entries')
    date = models.DateField()
    amount = models.FloatField()
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='kg')
    note = models.TextField(default='', blank=True)
    is_all = models.BooleanField(default=False, help_text='Marks harvest-all / end of season')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['season']),
        ]

    def __str__(self):
        return f"{self.amount} {self.unit} on {self.date}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.season.recompute_totals()

    def delete(self, *args, **kwargs):
        season = self.season
        super().delete(*args, **kwargs)
        season.recompute_totals()


class SeasonHistory(models.Model):
    """Read-only summary snapshot created when a season ends."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='season_history')
    season_name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    total_harvest_kg = models.FloatField(default=0.0)
    harvest_count = models.IntegerField(default=0)
    entry_count = models.IntegerField(default=0)
    initial_shrimp_quantity = models.IntegerField(default=0)
    current_shrimp_quantity = models.IntegerField(default=0)
    average_shrimp_weight_grams = models.FloatField(default=0.0)
    average_temp = models.FloatField(null=True, blank=True)
    average_ph = models.FloatField(null=True, blank=True)
    average_do = models.FloatField(null=True, blank=True)
    average_tds = models.FloatField(null=True, blank=True)
    notes = models.TextField(default='', blank=True)


# ========== WEATHER PREDICTION LOGGING & FEEDBACK LOOP ==========

class WeatherPrediction(models.Model):
    """
    Phase 3: Prediction logging system for accuracy tracking and model retraining
    Logs all weather forecasts with metrics and actual values for feedback loop
    """
    METRIC_CHOICES = [
        ('temperature', 'Temperature'),
        ('humidity', 'Humidity'),
        ('wind_speed', 'Wind Speed'),
        ('rainfall', 'Rainfall'),
        ('pressure', 'Pressure'),
    ]
    
    location = models.CharField(max_length=100, db_index=True)  # e.g., "calapan", "cebu"
    forecast_date = models.DateTimeField(db_index=True)  # When the forecast is for
    metric = models.CharField(max_length=50, choices=METRIC_CHOICES)
    
    # Forecast values
    ensemble_value = models.FloatField()  # Value from 3-API ensemble
    ml_corrected_value = models.FloatField()  # After ML correction
    ensemble_confidence = models.FloatField()  # 30-100% from ensemble
    ml_confidence = models.FloatField()  # 30-100% from ML models
    combined_confidence = models.FloatField(default=50.0)  # 60% ensemble + 40% ML
    
    # API breakdown
    open_meteo_value = models.FloatField(null=True, blank=True)
    weatherapi_value = models.FloatField(null=True, blank=True)
    nasa_value = models.FloatField(null=True, blank=True)
    
    # Actual verification (populated later when data arrives)
    actual_value = models.FloatField(null=True, blank=True)  # Observed/measured value
    actual_source = models.CharField(max_length=100, null=True, blank=True)  # Where actual came from
    verification_date = models.DateTimeField(null=True, blank=True, db_index=True)  # When verified
    
    # Accuracy metrics
    ensemble_error = models.FloatField(null=True, blank=True)  # abs(ensemble - actual)
    ml_error = models.FloatField(null=True, blank=True)  # abs(corrected - actual)
    improvement = models.FloatField(null=True, blank=True)  # ML vs ensemble improvement %
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['location', 'metric', '-forecast_date']),
            models.Index(fields=['location', '-created_at']),
        ]
    
    def calculate_errors(self):
        """Calculate and store accuracy metrics after actual value is known"""
        if self.actual_value is not None:
            self.ensemble_error = abs(self.ensemble_value - self.actual_value)
            self.ml_error = abs(self.ml_corrected_value - self.actual_value)
            self.improvement = max(0, (self.ensemble_error - self.ml_error) / self.ensemble_error * 100)
            self.verification_date = timezone.now()
            self.save()
    
    def __str__(self):
        return f"{self.location} {self.metric} on {self.forecast_date}"


class APIPerformance(models.Model):
    """
    Phase 3: Track API accuracy to enable dynamic ensemble weights
    Monthly snapshots of each API's performance per location
    """
    API_CHOICES = [
        ('open_meteo', 'Open-Meteo'),
        ('weatherapi', 'WeatherAPI'),
        ('nasa', 'NASA'),
    ]
    
    location = models.CharField(max_length=100, db_index=True)
    api_source = models.CharField(max_length=50, choices=API_CHOICES)
    month = models.DateField(db_index=True)  # First day of month for grouping
    
    # Accuracy metrics
    rmse = models.FloatField()  # Root Mean Squared Error
    mae = models.FloatField()  # Mean Absolute Error
    accuracy_percent = models.FloatField()  # Higher is better (0-100%)
    predictions_count = models.IntegerField()  # How many predictions tracked
    verified_count = models.IntegerField()  # How many have actuals
    
    # Dynamic weight (auto-adjusted based on accuracy)
    current_weight = models.FloatField(default=0.33)  # 0.0-1.0, normalized by 3 APIs
    previous_weight = models.FloatField(default=0.33)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['location', 'api_source', 'month']]
        ordering = ['-month', 'location']
    
    def __str__(self):
        return f"{self.location} - {self.api_source} ({self.month.strftime('%Y-%m')}): {self.accuracy_percent:.1f}%"


class ModelRetrainingLog(models.Model):
    """
    Phase 3: Log of automated monthly model retraining
    Track when models are retrained, what improved, and model versions
    """
    retraining_date = models.DateTimeField(auto_now_add=True, db_index=True)
    month_end = models.DateField()  # Month trained on
    
    # Statistics
    total_predictions = models.IntegerField()
    verified_predictions = models.IntegerField()
    
    # Metrics before/after
    previous_avg_rmse = models.FloatField()  # Average of all APIs/metrics
    new_avg_rmse = models.FloatField()
    improvement_percent = models.FloatField()  # (previous - new) / previous * 100
    
    # Model versions
    xgboost_version = models.CharField(max_length=50)  # v3, v4, etc.
    lstm_version = models.CharField(max_length=50)
    
    # Details
    notes = models.TextField(blank=True)
    success = models.BooleanField(default=True)
    errors = models.TextField(blank=True)  # Any retraining errors
    
    class Meta:
        ordering = ['-retraining_date']
    
    def __str__(self):
        return f"Retrain {self.month_end.strftime('%Y-%m')}: {self.improvement_percent:+.1f}% improvement"


class DailyGrowthMetric(models.Model):
    """Daily growth metrics for a season."""
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='growth_metrics')
    date = models.DateField()
    shrimp_count = models.IntegerField(help_text='Estimated or counted shrimp quantity')
    avg_weight_grams = models.FloatField(help_text='Average shrimp weight in grams')
    daily_weight_gain_grams = models.FloatField(default=0.0, help_text='Weight gained from previous day')
    daily_mortality_percent = models.FloatField(default=0.0, help_text='Mortality percentage for this day')
    feed_amount_grams = models.FloatField(default=0.0, help_text='Feed consumed this day')
    water_temperature = models.FloatField(null=True, blank=True, help_text='Water temperature in Celsius')
    water_ph = models.FloatField(null=True, blank=True)
    turbidity = models.FloatField(null=True, blank=True, help_text='Turbidity in NTU (from SensorReading)')
    dissolved_oxygen = models.FloatField(
        null=True, blank=True,
        help_text='Dissolved oxygen in mg/L (optional; not in SensorReading — may be estimated from turbidity)',
    )
    tds = models.FloatField(null=True, blank=True, help_text='Total dissolved solids')
    weather_condition = models.CharField(max_length=50, blank=True, help_text='e.g., sunny, rainy, cloudy')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        unique_together = [['season', 'date']]
        indexes = [
            models.Index(fields=['season', '-date']),
        ]
        verbose_name_plural = "Daily Growth Metrics"

    def __str__(self):
        return f"{self.season.name} - {self.date}: {self.avg_weight_grams}g avg"


class GrowthPrediction(models.Model):
    """ML predictions for shrimp growth performance."""
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='growth_predictions')
    prediction_date = models.DateField(help_text='Date when prediction was made')
    forecast_date = models.DateField(help_text='Date for which prediction is made')
    predicted_avg_weight_grams = models.FloatField()
    predicted_shrimp_count = models.IntegerField()
    predicted_survival_rate_percent = models.FloatField()
    estimated_harvest_date = models.DateField(null=True, blank=True)
    confidence_score = models.FloatField(default=0.0, help_text='Confidence percentage (0-100)')
    recommendation = models.TextField(blank=True, help_text='AI recommendation based on prediction')
    model_version = models.CharField(max_length=50, default='1.0', help_text='ML model version used')
    is_active = models.BooleanField(default=True, help_text='Most recent prediction for this forecast date')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-forecast_date', '-prediction_date']
        indexes = [
            models.Index(fields=['season', 'forecast_date']),
            models.Index(fields=['is_active', '-forecast_date']),
        ]

    def __str__(self):
        return f"Prediction for {self.season.name}: {self.forecast_date} → {self.predicted_avg_weight_grams}g"


class HistorySettings(models.Model):
    """Per-user settings for harvest reminders and notifications."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='history_settings')
    harvest_lead_days = models.IntegerField(default=90)
    harvest_time = models.TimeField(default='08:00:00')
    notification_email = models.EmailField(default='', blank=True)
    days_before_notification = models.IntegerField(default=2, help_text='Days before expected harvest to send reminder email')

    def __str__(self):
        return f"HistorySettings for {self.user.username}"
