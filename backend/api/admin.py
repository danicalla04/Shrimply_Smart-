from django.contrib import admin
from .models import (
    SensorReading, Threshold, Alert, WeatherCache, Feeder, FeedingLog, Report,
    Season, HarvestEntry, SeasonHistory, HistorySettings,
)

@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'temperature', 'ph', 'turbidity', 'tds']
    list_filter = ['timestamp']
    ordering = ['-timestamp']

@admin.register(Threshold)
class ThresholdAdmin(admin.ModelAdmin):
    list_display = ['parameter', 'min_value', 'max_value', 'unit']
    list_filter = ['parameter']

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'parameter', 'severity', 'value', 'resolved']
    list_filter = ['severity', 'parameter', 'resolved', 'timestamp']
    ordering = ['-timestamp']

@admin.register(WeatherCache)
class WeatherCacheAdmin(admin.ModelAdmin):
    list_display = ['city', 'timestamp']
    ordering = ['-timestamp']

@admin.register(Feeder)
class FeederAdmin(admin.ModelAdmin):
    list_display = ['id', 'auto_enabled', 'schedule_type', 'capacity_current', 'capacity_max', 'last_fed_at']
    list_filter = ['auto_enabled', 'schedule_type']
    ordering = ['-last_fed_at']

@admin.register(FeedingLog)
class FeedingLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'feeder', 'feed_type', 'portion_grams', 'capacity_before', 'capacity_after']
    list_filter = ['feed_type', 'timestamp']
    ordering = ['-timestamp']

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['title', 'report_type', 'status', 'start_date', 'end_date', 'created_at']
    list_filter = ['report_type', 'status', 'created_at']
    search_fields = ['title', 'notes']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'generated_at']
    
    fieldsets = (
        ('Report Information', {
            'fields': ('title', 'report_type', 'status')
        }),
        ('Date Range', {
            'fields': ('start_date', 'end_date')
        }),
        ('Report Data', {
            'fields': ('summary', 'insights', 'recommendations'),
            'classes': ('collapse',)
        }),
        ('File Export', {
            'fields': ('file_path', 'file_format'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'generated_at', 'notes')
        }),
    )
    
    actions = ['generate_report_summary']
    
    def generate_report_summary(self, request, queryset):
        for report in queryset:
            report.generate_summary()
            report.generate_insights()
            report.status = 'completed'
            report.save()
        self.message_user(request, f"{queryset.count()} reports generated successfully.")
    generate_report_summary.short_description = "Generate summary and insights"


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'start_date', 'end_date', 'is_active', 'total_harvest_kg', 'entry_count']
    list_filter = ['is_active', 'user']
    ordering = ['-start_date']


@admin.register(HarvestEntry)
class HarvestEntryAdmin(admin.ModelAdmin):
    list_display = ['date', 'season', 'amount', 'unit', 'is_all']
    list_filter = ['unit', 'is_all']
    ordering = ['-date']


@admin.register(SeasonHistory)
class SeasonHistoryAdmin(admin.ModelAdmin):
    list_display = ['season_name', 'user', 'start_date', 'end_date', 'total_harvest_kg']
    ordering = ['-start_date']


@admin.register(HistorySettings)
class HistorySettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'harvest_lead_days', 'harvest_time', 'notification_email']