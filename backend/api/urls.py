from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views_reports import ReportViewSet

router = DefaultRouter()
router.register(r'sensors', views.SensorReadingViewSet)
router.register(r'thresholds', views.ThresholdViewSet)
router.register(r'calibration', views.SensorCalibrationViewSet, basename='calibration')
router.register(r'alerts', views.AlertViewSet)
router.register(r'feeder', views.FeederViewSet)
router.register(r'reports', ReportViewSet, basename='report')
router.register(r'weather-forecasts', views.WeatherForecastViewSet, basename='weatherforecast')
router.register(r'seasons', views.SeasonViewSet, basename='season')
router.register(r'harvest-entries', views.HarvestEntryViewSet, basename='harvestentry')
router.register(r'season-history', views.SeasonHistoryViewSet, basename='seasonhistory')
router.register(r'history-settings', views.HistorySettingsViewSet, basename='historysettings')
router.register(r'feed-types', views.FeedTypeViewSet, basename='feedtype')
router.register(r'growth-metrics', views.DailyGrowthMetricViewSet, basename='growthmetric')
router.register(r'growth-predictions', views.GrowthPredictionViewSet, basename='growthprediction')

urlpatterns = [
    path('', include(router.urls)),
    path('update-sensors/', views.update_sensors, name='update_sensors'),
    path('update-feeder-telemetry/', views.update_feeder_telemetry, name='update_feeder_telemetry'),
    path('latest-feeder-telemetry/', views.latest_feeder_telemetry, name='latest_feeder_telemetry'),
    path('weather/', views.weather, name='weather'),
    path('weather/current/', views.weather_current, name='weather_current'),
    path('weather/tomorrow/', views.weather_tomorrow, name='weather_tomorrow'),
    path('weather/weekly/', views.weather_weekly, name='weather_weekly'),
    path('weather/complete/', views.weather_complete, name='weather_complete'),
    path('weather/municipalities/', views.weather_municipalities, name='weather_municipalities'),
    path('weather/hourly/', views.weather_hourly, name='weather_hourly'),
    path('weather/alerts/', views.weather_alerts, name='weather_alerts'),
    path('weather/ensemble-correct/', views.weather_ensemble_correct, name='weather_ensemble_correct'),
    path('weather/ml-info/', views.weather_ml_info, name='weather_ml_info'),
    path('weather/save-prediction/', views.weather_save_prediction, name='weather_save_prediction'),
    path('weather/verify-predictions/', views.weather_verify_predictions, name='weather_verify_predictions'),
    # Oriental Mindoro municipalities endpoints
    path('weather/locations/', views.weather_locations_list, name='weather_locations_list'),
    path('weather/calapan/', views.weather_calapan_focus, name='weather_calapan_focus'),
    path('weather/municipality/', views.weather_municipality_forecast, name='weather_municipality_forecast'),
    path('weather/ml-accuracy/', views.weather_ml_accuracy_report, name='weather_ml_accuracy_report'),
    path('water-quality/', views.water_quality_status, name='water_quality_status'),
    # Device ingestion endpoint (device -> backend -> MySQL database)
    path('device/readings/', views.device_readings, name='device_readings'),
    # Notification endpoints
    path('notify/harvest-reminder/', views.send_harvest_reminder, name='harvest-reminder'),
    # Buzzer control endpoints
    path('buzzer/control/', views.control_buzzer, name='buzzer_control'),
    path('buzzer/status/', views.get_buzzer_status, name='buzzer_status'),
]