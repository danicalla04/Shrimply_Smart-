"""
Field Evaluation API Endpoints
Real-time monitoring and reporting for 12-week field testing
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
import json
from pathlib import Path

from .field_evaluation import (
    FieldEvaluation_WeatherForecast,
    FieldEvaluation_WaterQuality,
    FieldEvaluation_FeederEvent,
    FieldEvaluation_SystemMetrics,
    FieldEvaluation_FieldLog,
    EvaluationAnalyzer,
)


# ============================================================================
# FIELD EVALUATION DATA LOGGING ENDPOINTS
# ============================================================================

@api_view(['POST'])
def log_weather_forecast(request):
    """
    Log a daily weather forecast vs. actual comparison
    POST /api/field-eval/weather-forecast/
    
    Body:
    {
        "location": "calapan",
        "forecast_date": "2026-04-05",
        "day_offset": 1,
        "predicted_temp": 32.5,
        "actual_temp": 31.8,
        "predicted_humidity": 75,
        "actual_humidity": 78,
        ...
    }
    """
    try:
        data = request.data
        forecast = FieldEvaluation_WeatherForecast.objects.create(
            location=data.get('location'),
            forecast_date=data.get('forecast_date'),
            day_offset=int(data.get('day_offset')),
            forecast_issued_at=timezone.now(),
            predicted_temp=float(data.get('predicted_temp')) if data.get('predicted_temp') else None,
            actual_temp=float(data.get('actual_temp')) if data.get('actual_temp') else None,
            predicted_humidity=float(data.get('predicted_humidity')) if data.get('predicted_humidity') else None,
            actual_humidity=float(data.get('actual_humidity')) if data.get('actual_humidity') else None,
            predicted_rainfall=float(data.get('predicted_rainfall')) if data.get('predicted_rainfall') else None,
            actual_rainfall=float(data.get('actual_rainfall')) if data.get('actual_rainfall') else None,
            predicted_wind_speed=float(data.get('predicted_wind_speed')) if data.get('predicted_wind_speed') else None,
            actual_wind_speed=float(data.get('actual_wind_speed')) if data.get('actual_wind_speed') else None,
            model_version=data.get('model_version', 'v3'),
            notes=data.get('notes'),
        )
        return Response({
            'status': 'success',
            'message': f'Logged forecast for {data.get("location")} ({data.get("day_offset")} days ahead)',
            'id': forecast.id,
            'temp_error': forecast.temp_error,
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def log_water_quality_measurement(request):
    """
    Log water quality sensor vs. lab validation measurement
    POST /api/field-eval/water-quality/
    """
    try:
        data = request.data
        measurement = FieldEvaluation_WaterQuality.objects.create(
            location=data.get('location'),
            measurement_date=data.get('measurement_date'),
            measurement_time=data.get('measurement_time'),
            sensor_ph=float(data.get('sensor_ph')) if data.get('sensor_ph') else None,
            sensor_temperature=float(data.get('sensor_temperature')) if data.get('sensor_temperature') else None,
            sensor_do=float(data.get('sensor_do')) if data.get('sensor_do') else None,
            sensor_turbidity=float(data.get('sensor_turbidity')) if data.get('sensor_turbidity') else None,
            lab_ph=float(data.get('lab_ph')) if data.get('lab_ph') else None,
            lab_temperature=float(data.get('lab_temperature')) if data.get('lab_temperature') else None,
            lab_do=float(data.get('lab_do')) if data.get('lab_do') else None,
            expert_risk_level=data.get('expert_risk_level'),
            validation_method=data.get('validation_method', 'sensor'),
            expert_notes=data.get('expert_notes'),
        )
        return Response({
            'status': 'success',
            'id': measurement.id,
            'sensor_accuracy': {
                'ph_error': measurement.ph_accuracy,
                'do_error': measurement.do_accuracy,
            }
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def log_feeder_event(request):
    """
    Log automated feeder dispensing event
    POST /api/field-eval/feeder-event/
    """
    try:
        data = request.data
        event = FieldEvaluation_FeederEvent.objects.create(
            location=data.get('location'),
            event_timestamp=data.get('event_timestamp') or timezone.now(),
            test_group=data.get('test_group'),
            planned_amount_grams=float(data.get('planned_amount_grams')),
            actual_dispensed_grams=float(data.get('actual_dispensed_grams')) if data.get('actual_dispensed_grams') else None,
            feeder_motor_runtime_seconds=float(data.get('feeder_motor_runtime_seconds')) if data.get('feeder_motor_runtime_seconds') else None,
            api_to_feeder_latency_ms=int(data.get('api_to_feeder_latency_ms')) if data.get('api_to_feeder_latency_ms') else None,
            shrimp_biomass_estimate_kg=float(data.get('shrimp_biomass_estimate_kg')) if data.get('shrimp_biomass_estimate_kg') else None,
            system_error_code=data.get('system_error_code', 'none'),
            error_message=data.get('error_message'),
            shrimp_feeding_response=data.get('shrimp_feeding_response'),
            notes=data.get('notes'),
        )
        return Response({
            'status': 'success',
            'id': event.id,
            'accuracy_percent': event.dispensing_accuracy_percent,
            'latency_ms': event.api_to_feeder_latency_ms,
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def log_system_metrics(request):
    """
    Log server performance metrics
    POST /api/field-eval/system-metrics/
    """
    try:
        data = request.data
        metrics = FieldEvaluation_SystemMetrics.objects.create(
            measurement_timestamp=timezone.now(),
            api_uptime_percent=float(data.get('api_uptime_percent')),
            api_latency_ms_p50=int(data.get('api_latency_ms_p50')) if data.get('api_latency_ms_p50') else None,
            api_latency_ms_p95=int(data.get('api_latency_ms_p95')) if data.get('api_latency_ms_p95') else None,
            websocket_latency_ms=int(data.get('websocket_latency_ms')) if data.get('websocket_latency_ms') else None,
            cpu_utilization_percent=float(data.get('cpu_utilization_percent')) if data.get('cpu_utilization_percent') else None,
            memory_usage_percent=float(data.get('memory_usage_percent')) if data.get('memory_usage_percent') else None,
            sensor_network_uptime_percent=float(data.get('sensor_network_uptime_percent')) if data.get('sensor_network_uptime_percent') else None,
            concurrent_users_count=int(data.get('concurrent_users_count', 0)),
            errors_count_last_1h=int(data.get('errors_count_last_1h', 0)),
            notes=data.get('notes'),
        )
        return Response({
            'status': 'success',
            'id': metrics.id,
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def log_field_observation(request):
    """
    Log daily field observer notes
    POST /api/field-eval/field-log/
    """
    try:
        data = request.data
        log = FieldEvaluation_FieldLog.objects.create(
            location=data.get('location'),
            log_date=data.get('log_date') or timezone.now().date(),
            observer_name=data.get('observer_name'),
            temp_min_celsius=float(data.get('temp_min_celsius')) if data.get('temp_min_celsius') else None,
            temp_max_celsius=float(data.get('temp_max_celsius')) if data.get('temp_max_celsius') else None,
            rainfall_mm=float(data.get('rainfall_mm')) if data.get('rainfall_mm') else None,
            wind_speed_kmh=float(data.get('wind_speed_kmh')) if data.get('wind_speed_kmh') else None,
            water_clarity=data.get('water_clarity'),
            water_color=data.get('water_color'),
            water_odor_normal=data.get('water_odor_normal', True),
            shrimp_feeding_response=data.get('shrimp_feeding_response'),
            feed_residual=data.get('feed_residual'),
            feeder_errors_observed=data.get('feeder_errors_observed', False),
            sensors_cleaned=data.get('sensors_cleaned', False),
            general_notes=data.get('general_notes'),
        )
        return Response({
            'status': 'success',
            'id': log.id,
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# FIELD EVALUATION ANALYSIS ENDPOINTS
# ============================================================================

@api_view(['GET'])
def weather_forecast_accuracy(request):
    """
    Get weather forecast accuracy metrics
    GET /api/field-eval/weather-accuracy/?location=calapan&days=7
    """
    try:
        location = request.query_params.get('location')
        days = int(request.query_params.get('days', 7))
        
        metrics = EvaluationAnalyzer.weather_forecast_metrics(location=location, days_ago=days)
        
        return Response({
            'status': 'success',
            'metrics': metrics,
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def water_quality_validation(request):
    """
    Get water quality sensor validation metrics (sensor vs lab)
    GET /api/field-eval/water-quality-validation/?location=calapan&days=30
    """
    try:
        location = request.query_params.get('location')
        days = int(request.query_params.get('days', 30))
        
        metrics = EvaluationAnalyzer.water_quality_validation_metrics(location=location, days_ago=days)
        
        return Response({
            'status': 'success',
            'metrics': metrics,
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def feeder_performance(request):
    """
    Get feeder dispensing accuracy and reliability metrics
    GET /api/field-eval/feeder-performance/?location=calapan&group=control&days=30
    """
    try:
        location = request.query_params.get('location')
        group = request.query_params.get('group')  # control or test
        days = int(request.query_params.get('days', 30))
        
        metrics = EvaluationAnalyzer.feeder_performance_summary(
            location=location,
            days_ago=days,
            test_group=group
        )
        
        return Response({
            'status': 'success',
            'metrics': metrics,
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def system_health(request):
    """
    Get overall system availability and performance metrics
    GET /api/field-eval/system-health/?days=7
    """
    try:
        days = int(request.query_params.get('days', 7))
        
        metrics = EvaluationAnalyzer.system_health_summary(days_ago=days)
        
        return Response({
            'status': 'success',
            'metrics': metrics,
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def evaluation_dashboard(request):
    """
    Get comprehensive field evaluation dashboard summary
    GET /api/field-eval/dashboard/?days=7&locations=calapan,pinamalayan
    """
    try:
        days = int(request.query_params.get('days', 7))
        locations = request.query_params.get('locations', '').split(',')
        locations = [l.strip() for l in locations if l.strip()]
        
        dashboard = {
            'timestamp': timezone.now().isoformat(),
            'period_days': days,
            'weather_forecast': {},
            'water_quality': {},
            'feeder_performance': {},
            'system_health': {},
        }
        
        # Weather metrics
        if not locations:
            dashboard['weather_forecast'] = EvaluationAnalyzer.weather_forecast_metrics(days_ago=days)
        else:
            for loc in locations:
                dashboard['weather_forecast'][loc] = EvaluationAnalyzer.weather_forecast_metrics(
                    location=loc,
                    days_ago=days
                )
        
        # Water quality metrics
        if not locations:
            dashboard['water_quality'] = EvaluationAnalyzer.water_quality_validation_metrics(days_ago=days)
        else:
            for loc in locations:
                dashboard['water_quality'][loc] = EvaluationAnalyzer.water_quality_validation_metrics(
                    location=loc,
                    days_ago=days
                )
        
        # Feeder performance
        for group in ['control', 'test']:
            if not locations:
                dashboard['feeder_performance'][group] = EvaluationAnalyzer.feeder_performance_summary(
                    days_ago=days,
                    test_group=group
                )
            else:
                dashboard['feeder_performance'][group] = {}
                for loc in locations:
                    dashboard['feeder_performance'][group][loc] = EvaluationAnalyzer.feeder_performance_summary(
                        location=loc,
                        days_ago=days,
                        test_group=group
                    )
        
        # System health
        dashboard['system_health'] = EvaluationAnalyzer.system_health_summary(days_ago=days)
        
        return Response(dashboard)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def generate_evaluation_report(request):
    """
    Generate PDF/JSON evaluation report for time period
    GET /api/field-eval/report/?start_date=2026-04-01&end_date=2026-06-30
    """
    try:
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        locations = request.query_params.get('locations', '').split(',')
        locations = [l.strip() for l in locations if l.strip()]
        
        # Get all evaluation data for period
        weather_data = FieldEvaluation_WeatherForecast.objects.filter(
            forecast_date__gte=start_date,
            forecast_date__lte=end_date
        )
        if locations:
            weather_data = weather_data.filter(location__in=locations)
        
        water_data = FieldEvaluation_WaterQuality.objects.filter(
            measurement_date__gte=start_date,
            measurement_date__lte=end_date
        )
        if locations:
            water_data = water_data.filter(location__in=locations)
        
        feeder_data = FieldEvaluation_FeederEvent.objects.filter(
            event_timestamp__gte=start_date,
            event_timestamp__lte=end_date
        )
        if locations:
            feeder_data = feeder_data.filter(location__in=locations)
        
        report = {
            'period': {'start': start_date, 'end': end_date},
            'summary': {
                'weather_forecasts_logged': weather_data.count(),
                'water_quality_measurements': water_data.count(),
                'feeder_events_logged': feeder_data.count(),
            },
            'weather_forecast_accuracy': EvaluationAnalyzer.weather_forecast_metrics(days_ago=999),
            'water_quality_validation': EvaluationAnalyzer.water_quality_validation_metrics(days_ago=999),
            'feeder_control_group': EvaluationAnalyzer.feeder_performance_summary(test_group='control', days_ago=999),
            'feeder_test_group': EvaluationAnalyzer.feeder_performance_summary(test_group='test', days_ago=999),
            'system_health': EvaluationAnalyzer.system_health_summary(days_ago=999),
        }
        
        return Response({
            'status': 'success',
            'report': report,
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


