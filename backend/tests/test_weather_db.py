"""
Test script to populate weather forecast database
Run with: python manage.py shell < test_weather_db.py
Or: python test_weather_db.py (if Django setup is configured)
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
django.setup()

from api.weather_predictor import weather_predictor
from api.models import WeatherForecast
from datetime import datetime

def test_weather_database():
    print("=" * 60)
    print("Testing Weather Forecast Database Integration")
    print("=" * 60)
    
    # Test 1: Get current weather and save to DB
    print("\n1. Fetching current weather for Oriental Mindoro...")
    current = weather_predictor.get_current_weather('Oriental Mindoro', save_to_db=True)
    if current:
        print(f"   ✅ Current: {current['temperature']}°C, {current['description']}")
        print(f"   📍 Location: {current['city']}, {current['country']}")
    else:
        print("   ❌ Failed to fetch current weather")
    
    # Test 2: Get tomorrow's forecast and save to DB
    print("\n2. Predicting tomorrow's weather...")
    tomorrow = weather_predictor.predict_tomorrow('Oriental Mindoro', save_to_db=True)
    if tomorrow:
        print(f"   ✅ Tomorrow: {tomorrow['max']}°C / {tomorrow['min']}°C, {tomorrow['description']}")
    else:
        print("   ❌ Failed to predict tomorrow's weather")
    
    # Test 3: Get weekly forecast and save to DB
    print("\n3. Generating 7-day forecast...")
    weekly = weather_predictor.predict_weekly('Oriental Mindoro', days=7, save_to_db=True)
    if weekly:
        print(f"   ✅ Weekly forecast generated: {len(weekly)} days")
        for day in weekly[:3]:  # Show first 3 days
            print(f"      - {day['day']}: {day['max']}°C, {day['description']}")
    else:
        print("   ❌ Failed to generate weekly forecast")
    
    # Test 4: Query database
    print("\n4. Querying database...")
    total_forecasts = WeatherForecast.objects.count()
    print(f"   📊 Total forecasts in database: {total_forecasts}")
    
    # Count by type
    current_count = WeatherForecast.objects.filter(forecast_type='current').count()
    tomorrow_count = WeatherForecast.objects.filter(forecast_type='tomorrow').count()
    daily_count = WeatherForecast.objects.filter(forecast_type='daily').count()
    
    print(f"   📊 Current weather: {current_count}")
    print(f"   📊 Tomorrow forecasts: {tomorrow_count}")
    print(f"   📊 Daily forecasts: {daily_count}")
    
    # Test 5: Check impact assessments
    print("\n5. Checking impact assessments...")
    forecasts_with_impacts = WeatherForecast.objects.exclude(temperature_impact='')
    if forecasts_with_impacts.exists():
        print(f"   ✅ {forecasts_with_impacts.count()} forecasts have impact assessments")
        sample = forecasts_with_impacts.first()
        print(f"   📊 Sample: {sample.city} - Temp Impact: {sample.temperature_impact}")
        if sample.recommendations:
            print(f"   💡 Recommendations: {len(sample.recommendations)} suggestions")
            for rec in sample.recommendations[:2]:
                print(f"      - {rec}")
    else:
        print("   ⚠️ No forecasts with impact assessments found")
    
    # Test 6: Recent forecasts
    print("\n6. Recent forecasts...")
    recent = WeatherForecast.objects.all().order_by('-created_at')[:5]
    for forecast in recent:
        print(f"   📅 {forecast.forecast_date} ({forecast.get_forecast_type_display()}): {forecast.city}, {forecast.temperature}°C")
    
    print("\n" + "=" * 60)
    print("✅ Database integration test complete!")
    print("=" * 60)
    
    # Summary
    print(f"\n📈 Summary:")
    print(f"   - Weather forecasts stored: {total_forecasts}")
    print(f"   - Cities covered: {WeatherForecast.objects.values('city').distinct().count()}")
    print(f"   - API endpoint available at: /api/weather-forecasts/")
    print(f"   - View stats at: /api/weather-forecasts/stats/")
    print(f"   - Current weather: /api/weather-forecasts/current/?city=Oriental%20Mindoro")
    print(f"   - Tomorrow: /api/weather-forecasts/tomorrow/?city=Oriental%20Mindoro")
    print(f"   - Weekly: /api/weather-forecasts/weekly/?city=Oriental%20Mindoro")

if __name__ == '__main__':
    test_weather_database()
