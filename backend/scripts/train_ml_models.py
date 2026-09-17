#!/usr/bin/env python3
"""
Train production-grade ML models for weather forecasting
Uses ensemble methods (XGBoost) for high accuracy
"""

import pandas as pd
import numpy as np
import os
import joblib
import warnings
from pathlib import Path
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import xgboost as xgb

warnings.filterwarnings('ignore')

class MLModelTrainer:
    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.data_dir = self.project_root / 'dataset' / 'data'
        self.models_dir = self.project_root / 'dataset' / 'models'
        self.models_dir.mkdir(parents=True, exist_ok=True)
        print(f"📂 Project Root: {self.project_root}")
        print(f"📂 Models saved to: {self.models_dir}")
    
    def train_weather_models(self):
        """Train ensemble models for weather forecasting"""
        print("\n" + "="*60)
        print("🌦️ TRAINING WEATHER FORECAST MODELS")
        print("="*60)
        
        # Load dataset
        dataset_path = self.data_dir / 'weather_comprehensive.csv'
        if not dataset_path.exists():
            print(f"❌ Dataset not found: {dataset_path}")
            print("   Run: python generate_weather_dataset.py")
            return False
        
        df = pd.read_csv(dataset_path)
        print(f"✓ Loaded {len(df):,} weather records")
        
        # Train separate models for each weather parameter
        weather_targets = {
            'temperature_max': 'Temperature (Max)',
            'humidity': 'Humidity',
            'rainfall_mm': 'Rainfall',
            'wind_speed_kmh': 'Wind Speed',
            'pressure_mb': 'Pressure'
        }
        
        feature_cols = [
            'latitude', 'longitude', 'month', 'day_of_year',
            'temperature_avg', 'humidity', 'rainfall_mm',
            'wind_speed_kmh', 'pressure_mb', 'cloud_cover_percent'
        ]
        
        all_metrics = {}
        
        for target, target_name in weather_targets.items():
            print(f"\n📍 Training model for {target_name}...")
            
            # Prepare data
            X = df[feature_cols].fillna(df[feature_cols].mean())
            y = df[target].fillna(df[target].mean())
            
            # Split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Scale
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train XGBoost
            model = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                verbosity=0
            )
            model.fit(X_train, y_train)
            
            # Evaluate
            y_pred = model.predict(X_test)
            r2 = r2_score(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            mae = mean_absolute_error(y_test, y_pred)
            
            print(f"  ✓ R² Score: {r2:.4f}")
            print(f"  ✓ RMSE: {rmse:.4f}")
            print(f"  ✓ MAE: {mae:.4f}")
            
            # Save
            model_path = self.models_dir / f'weather_{target}_xgboost.pkl'
            joblib.dump(model, model_path)
            print(f"  ✓ Saved: {model_path}")
            
            all_metrics[target] = {'r2': r2, 'rmse': rmse, 'mae': mae}
        
        # Save features and scaler
        features_path = self.models_dir / 'weather_features.pkl'
        joblib.dump(feature_cols, features_path)
        
        print("\n📊 Weather Model Metrics Summary:")
        print(f"{'Parameter':<20} {'R² Score':<12} {'RMSE':<10} {'MAE':<10}")
        print("-" * 52)
        for param, metric in all_metrics.items():
            print(f"{param:<20} {metric['r2']:<12.4f} {metric['rmse']:<10.4f} {metric['mae']:<10.4f}")
        
        return True

if __name__ == '__main__':
    trainer = MLModelTrainer()
    
    print("\n🚀 Starting ML Model Training Pipeline")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Train weather models
    trainer.train_weather_models()
    
    print("\n" + "="*60)
    print("✅ ML Training Pipeline Complete!")
    print("="*60)
    print("\n💡 Next steps:")
    print("   1. Restart the backend server")
    print("   2. Test predictions in the application")
    print("   3. Monitor model performance in production")
