#!/usr/bin/env python3
"""
Generate comprehensive weather forecast training dataset for Philippines aquaculture regions.
Creates realistic weather patterns with seasonal variations and anomalies.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def generate_weather_dataset(num_days=1095, start_date='2022-01-01'):
    """
    Generate comprehensive weather dataset with realistic Philippine weather patterns
    Covers multiple locations with regional variations
    """
    print(f"🌦️ Generating {num_days} days of weather data from {start_date}...")
    
    locations = {
        'Calapan': {'lat': 13.411, 'lon': 121.180, 'region': 'Mindoro', 'typhoon_factor': 1.0},
        'Pinamalayan': {'lat': 13.015, 'lon': 121.478, 'region': 'Mindoro', 'typhoon_factor': 0.95},
        'Dagupan': {'lat': 16.043, 'lon': 120.340, 'region': 'Pangasinan', 'typhoon_factor': 1.1},
        'Bacolod': {'lat': 10.676, 'lon': 122.950, 'region': 'Negros', 'typhoon_factor': 0.8},
    }
    
    all_data = []
    
    for location, loc_info in locations.items():
        print(f"\n  📍 Generating data for {location}...")
        
        location_data = []
        start = datetime.strptime(start_date, '%Y-%m-%d')
        
        for day in range(num_days):
            current_date = start + timedelta(days=day)
            month = current_date.month
            day_of_year = current_date.timetuple().tm_yday
            
            # --- Temperature (seasonal pattern for Philippines) ---
            # Dry season (Nov-May): cooler, Wet season (Jun-Oct): hotter
            if month in [3, 4, 5]:  # Hot season
                base_temp = 32
            elif month in [11, 12, 1, 2]:  # Cool season
                base_temp = 25
            else:  # Wet season
                base_temp = 28
            
            temp_variation = 3 * np.sin(2 * np.pi * day_of_year / 365)
            temp_noise = np.random.normal(0, 1.5)
            temperature_max = base_temp + 3 + temp_variation + temp_noise
            temperature_min = base_temp - 3 + temp_variation + temp_noise
            temperature_avg = (temperature_max + temperature_min) / 2
            
            temperature_max = np.clip(temperature_max, 20, 40)
            temperature_min = np.clip(temperature_min, 15, 35)
            
            # --- Humidity (higher during wet season) ---
            if month in [6, 7, 8, 9, 10]:  # Wet season
                base_humidity = 80
            else:
                base_humidity = 65
            
            humidity_variation = 10 * np.sin(2 * np.pi * day_of_year / 365)
            humidity_noise = np.random.normal(0, 3)
            humidity = base_humidity + humidity_variation + humidity_noise
            humidity = np.clip(humidity, 40, 100)
            
            # --- Rainfall (seasonal monsoon patterns) ---
            if month in [6, 7, 8, 9]:  # Southwest monsoon (peak)
                base_rainfall = 300
                rainfall_variability = 200
            elif month in [11, 12]:  # Northeast monsoon
                base_rainfall = 150
                rainfall_variability = 100
            elif month in [5, 10]:  # Transition
                base_rainfall = 100
                rainfall_variability = 80
            else:  # Dry season
                base_rainfall = 30
                rainfall_variability = 40
            
            rainfall = np.random.exponential(base_rainfall / 3)
            rainfall = min(rainfall, base_rainfall + rainfall_variability)
            rainfall = np.clip(rainfall, 0, 500)
            
            # Add typhoon events (rare, high rainfall)
            if np.random.random() < 0.05 * loc_info['typhoon_factor'] and month in [7, 8, 9, 10]:
                rainfall = np.random.uniform(200, 500)
            
            # --- Wind Speed (knots, increases with tropical storms) ---
            base_wind = 15 if month in [6, 7, 8, 9] else 10
            wind_variation = 5 * np.sin(2 * np.pi * day_of_year / 365)
            wind_noise = np.random.exponential(3)  # Occasional strong gusts
            wind_speed = base_wind + wind_variation + wind_noise
            wind_speed = np.clip(wind_speed, 3, 80)
            
            # --- Wind Direction (NE trades in dry, SW monsoon in wet) ---
            if month in [6, 7, 8, 9, 10]:  # Southwest monsoon
                wind_direction = 225 + np.random.normal(0, 30)
            else:  # Northeast trades
                wind_direction = 45 + np.random.normal(0, 30)
            wind_direction = wind_direction % 360
            
            # --- Pressure (millibars) ---
            base_pressure = 1013
            seasonal_pressure = 5 * np.sin(2 * np.pi * day_of_year / 365)
            pressure_noise = np.random.normal(0, 2)
            pressure = base_pressure + seasonal_pressure + pressure_noise
            pressure = np.clip(pressure, 990, 1030)
            
            # --- Visibility (km, reduced by rain) ---
            base_visibility = 10
            rain_effect = -0.05 * rainfall  # Reduces with rainfall
            visibility = base_visibility + rain_effect + np.random.normal(0, 0.5)
            visibility = np.clip(visibility, 0.5, 15)
            
            # --- UV Index ---
            uv_base = 8 if month in [3, 4, 5] else 6
            cloud_cover_effect = -0.05 * humidity
            uv_index = uv_base + cloud_cover_effect + np.random.normal(0, 0.5)
            uv_index = np.clip(uv_index, 1, 12)
            
            # --- Cloud Cover (%) ---
            if month in [6, 7, 8, 9, 10]:  # Wet season
                base_cloud = 75
            else:
                base_cloud = 40
            
            cloud_cover = base_cloud + np.random.normal(0, 15)
            cloud_cover = np.clip(cloud_cover, 0, 100)
            
            # --- Solar Radiation (MJ/m2/day) ---
            solar_base = 18 if month in [3, 4, 5] else 16
            cloud_effect = -0.1 * cloud_cover
            solar_rad = solar_base + cloud_effect + np.random.normal(0, 1)
            solar_rad = np.clip(solar_rad, 5, 25)
            
            # --- Evapotranspiration (mm/day) ---
            et_base = max(0, temperature_avg - 10) * 0.15
            humidity_effect = -et_base * (humidity / 100)
            wind_effect = wind_speed * 0.02
            et = et_base + humidity_effect + wind_effect
            et = np.clip(et, 0, 10)
            
            # Create record
            record = {
                'date': current_date.strftime('%Y-%m-%d'),
                'location': location,
                'latitude': loc_info['lat'],
                'longitude': loc_info['lon'],
                'region': loc_info['region'],
                'month': month,
                'day_of_year': day_of_year,
                'temperature_max': round(temperature_max, 1),
                'temperature_min': round(temperature_min, 1),
                'temperature_avg': round(temperature_avg, 1),
                'humidity': round(humidity, 1),
                'rainfall_mm': round(rainfall, 2),
                'wind_speed_kmh': round(wind_speed * 1.852, 1),  # knots to km/h
                'wind_direction_deg': round(wind_direction, 0),
                'pressure_mb': round(pressure, 1),
                'visibility_km': round(visibility, 1),
                'uv_index': round(uv_index, 1),
                'cloud_cover_percent': round(cloud_cover, 1),
                'solar_radiation_mj': round(solar_rad, 2),
                'evapotranspiration_mm': round(et, 2),
            }
            
            location_data.append(record)
        
        all_data.extend(location_data)
        print(f"  ✓ Generated {len(location_data)} records for {location}")
    
    # Create DataFrame
    df = pd.DataFrame(all_data)
    
    # Add derived features for ML
    df['season'] = df['month'].apply(
        lambda m: 'Dry' if m in [1, 2, 3, 4, 5] else ('Wet' if m in [6, 7, 8, 9, 10] else 'Transition')
    )
    
    # Temperature range
    df['temp_range'] = df['temperature_max'] - df['temperature_min']
    
    # Weather classification
    def classify_weather(row):
        if row['rainfall_mm'] > 200:
            return 'Heavy Rain'
        elif row['rainfall_mm'] > 50:
            return 'Moderate Rain'
        elif row['rainfall_mm'] > 10:
            return 'Light Rain'
        elif row['humidity'] < 50 and row['wind_speed_kmh'] < 15:
            return 'Clear'
        elif row['cloud_cover_percent'] > 70:
            return 'Cloudy'
        else:
            return 'Partly Cloudy'
    
    df['weather_condition'] = df.apply(classify_weather, axis=1)
    
    # Save dataset
    output_path = os.path.join(os.path.dirname(__file__), '..', '..', 'dataset', 'data', 'weather_comprehensive.csv')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    
    print(f"\n✅ Dataset saved to: {output_path}")
    print(f"   Total records: {len(df):,}")
    print(f"   Locations: {df['location'].nunique()}")
    print(f"   Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"\n📊 Dataset Statistics:")
    print(df[['temperature_max', 'humidity', 'rainfall_mm', 'wind_speed_kmh', 'pressure_mb']].describe())
    print(f"\n🌦️ Weather distribution:")
    print(df['weather_condition'].value_counts())
    
    return df

if __name__ == '__main__':
    df = generate_weather_dataset(num_days=1095)  # 3 years
    print("\n✨ Weather dataset generation complete!")
