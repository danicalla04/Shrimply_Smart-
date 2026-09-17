# Weather extensions for hourly forecast and alerts

def get_hourly_forecast(self, location: str):
    """Get hourly forecast for next 24 hours from OpenWeather API"""
    try:
        from datetime import datetime
        import requests
        
        city_name = location.split(',')[0].strip()
        
        # Fetch 5-day/3-hour forecast
        url = f'https://api.openweathermap.org/data/2.5/forecast?q={location},PH&appid={self.openweather_api_key}&units=metric'
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            url = f'https://api.openweathermap.org/data/2.5/forecast?q={city_name},PH&appid={self.openweather_api_key}&units=metric'
            response = requests.get(url, timeout=10)
        
        response.raise_for_status()
        data = response.json()
        
        hourly_data = []
        
        # Get next 24 hours (8 intervals of 3 hours each)
        for item in data['list'][:8]:
            dt = datetime.fromtimestamp(item['dt'])
            
            hourly_data.append({
                'datetime': dt.isoformat(),
                'time': dt.strftime('%I:%M %p'),
                'hour': dt.strftime('%I %p'),
                'temperature': round(item['main']['temp'], 1),
                'feels_like': round(item['main']['feels_like'], 1),
                'humidity': item['main']['humidity'],
                'pressure': round(item['main']['pressure'], 1),
                'wind_speed': round(item['wind']['speed'] * 3.6, 1),
                'wind_direction': item['wind'].get('deg', 0),
                'wind_gust': round(item['wind'].get('gust', 0) * 3.6, 1),
                'precipitation': round(item.get('rain', {}).get('3h', 0), 2),
                'snow': round(item.get('snow', {}).get('3h', 0), 2),
                'clouds': item['clouds']['all'],
                'description': item['weather'][0]['description'].capitalize(),
                'icon': item['weather'][0]['icon'],
                'icon_url': f"https://openweathermap.org/img/wn/{item['weather'][0]['icon']}@2x.png",
                'pop': int(item.get('pop', 0) * 100),
                'visibility': round(item.get('visibility', 10000) / 1000, 1)
            })
        
        return hourly_data
        
    except Exception as e:
        print(f"[ERROR] Error fetching hourly forecast: {e}")
        return []

def get_weather_alerts(self, location: str):
    """Get weather alerts and warnings"""
    from datetime import datetime
    
    alerts = []
    
    try:
        current = self.get_current_weather_enhanced(location, save_to_db=False)
        weekly = self.predict_weekly_enhanced(location, 7, save_to_db=False)
        
        if not current:
            return alerts
        
        # Temperature alerts
        if current['temperature'] > 35:
            alerts.append({
                'type': 'extreme_heat', 'severity': 'high', 'title': 'Extreme Heat Warning',
                'message': f"Temperature is {current['temperature']}°C. Critical risk to shrimp health.",
                'recommendations': ['Increase aeration immediately', 'Monitor water quality closely'],
                'icon': '🔥', 'color': 'red'
            })
        elif current['temperature'] > 32:
            alerts.append({
                'type': 'high_temperature', 'severity': 'medium', 'title': 'High Temperature Alert',
                'message': f"Temperature is {current['temperature']}°C. Monitor shrimp behavior.",
                'recommendations': ['Increase water circulation', 'Monitor water quality'],
                'icon': '🌡️', 'color': 'orange'
            })
        
        # Heavy rain alerts
        for day in weekly[:3]:
            if day.get('precipMm', 0) > 50:
                alerts.append({
                    'type': 'heavy_rain', 'severity': 'high',
                    'title': f"Heavy Rainfall Expected - {day['day']}",
                    'message': f"Expected rainfall: {day['precipMm']}mm. Prepare for flooding.",
                    'recommendations': ['Check pond drainage systems', 'Monitor salinity levels'],
                    'icon': '🌧️', 'color': 'blue', 'date': day['date']
                })
        
        # Strong wind alerts
        if current.get('windKmh', 0) > 40:
            alerts.append({
                'type': 'strong_wind', 'severity': 'medium', 'title': 'Strong Wind Warning',
                'message': f"Wind speed: {current['windKmh']} km/h. Secure equipment.",
                'recommendations': ['Secure loose equipment', 'Check aerator stability'],
                'icon': '💨', 'color': 'yellow'
            })
        
        # Typhoon season
        month = datetime.now().month
        if month in [6, 7, 8, 9, 10, 11]:
            typhoon_risk = 'high' if month in [8, 9, 10] else 'medium'
            alerts.append({
                'type': 'typhoon_season', 'severity': 'info', 'title': 'Typhoon Season Active',
                'message': f'Peak typhoon season. Risk level: {typhoon_risk.upper()}',
                'recommendations': ['Monitor weather updates daily', 'Maintain emergency supplies'],
                'icon': '🌀', 'color': 'purple'
            })
        
        return alerts
        
    except Exception as e:
        print(f"[ERROR] Error generating weather alerts: {e}")
        return []
