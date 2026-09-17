"""
DEPRECATED — Legacy Weather Prediction Service.

This module is superseded by ``enhanced_weather_predictor.py`` which provides
an improved ML ensemble (XGBoost v3 + LSTM + ARIMA) with Philippine monsoon
and typhoon pattern adjustments.

The class is retained for backward-compatibility with existing test scripts
(``tests/run_inference_test.py``, ``tests/test_model_interface.py``, etc.)
but is no longer instantiated at module level to avoid slow startup.

Use ``ml_loader.get_weather_predictor()`` instead for production code.
"""

import pandas as pd
import os
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')
import numpy as np
from statsmodels.tsa.arima.model import ARIMA
import json

# Optional heavy imports — guarded so the module can still be imported
# even if TensorFlow or XGBoost are not installed.
try:
    import joblib
except ImportError:
    joblib = None
try:
    import tensorflow as tf
    from tensorflow import keras
except ImportError:
    tf = None
    keras = None
try:
    import xgboost as xgb
except ImportError:
    xgb = None

class WeatherPredictor:
    def __init__(self):
        self.csv_path = Path(__file__).resolve().parent.parent.parent / 'dataset' / 'data' / 'philippines_weather_raw.csv'
        self.models_dir = Path(__file__).resolve().parent.parent.parent / 'dataset' / 'models'
        self.data = None
        self.models = {}
        self.scalers = {}
        # per-location LSTM output mappings (name -> {target: index})
        self.lstm_mappings = {}
        self.last_data = None
        self.load_data()
        self.load_models()
    
    def load_data(self):
        """Load weather data from CSV file"""
        try:
            if os.path.exists(self.csv_path):
                self.data = pd.read_csv(self.csv_path, sep=',', on_bad_lines='skip', engine='python')
                self.data['date'] = pd.to_datetime(self.data['date'])
                print(f"✅ Loaded {len(self.data)} weather records from CSV")
            else:
                print(f"⚠️ Weather CSV not found at {self.csv_path}")
                self.data = None
        except pd.errors.ParserError as e:
            print(f"❌ Error loading weather CSV: {e}")
            self.data = None
        except Exception as e:
            print(f"❌ Error loading weather CSV: {e}")
            self.data = None
    
    def load_models(self):
        """Load trained ML models"""
        try:
            model_files = ['temperature_model.pkl', 'humidity_model.pkl', 'rainfall_model.pkl', 
                          'wind_speed_model.pkl', 'pressure_model.pkl', 'condition_model.pkl',
                          'condition_encoder.pkl', 'last_data.pkl']
            
            for file in model_files:
                path = self.models_dir / file
                if path.exists():
                    self.models[file.replace('.pkl', '')] = joblib.load(path)
                    print(f"✅ Loaded {file}")
                else:
                    print(f"⚠️ Model file not found: {file}")

            # Load scaler artifacts (temperature_scaler and any scaler_*.pkl)
            scaler_path = self.models_dir / 'temperature_scaler.pkl'
            if scaler_path.exists():
                try:
                    self.scalers['temperature'] = joblib.load(scaler_path)
                    print('✅ Loaded temperature_scaler.pkl')
                except Exception as e:
                    print(f'⚠️ Failed to load temperature_scaler.pkl: {e}')

            for s in self.models_dir.glob('scaler_*.pkl'):
                try:
                    name = s.stem.replace('scaler_', '')
                    self.scalers[name] = joblib.load(s)
                    print(f"✅ Loaded scaler: {s.name}")
                except Exception as e:
                    print(f"⚠️ Failed to load scaler {s.name}: {e}")

            # Load any TensorFlow SavedModel LSTMs under models/ prefixed with saved_
            for saved in self.models_dir.glob('saved_*/'):
                name = saved.name.replace('saved_', '')
                loaded = False
                try:
                    # Try Keras load (works for .keras/.h5); Keras 3 may not support legacy SavedModel
                    try:
                        model = keras.models.load_model(saved, compile=False, safe_mode=False)
                    except TypeError:
                        model = keras.models.load_model(saved, compile=False)
                    self.models[f'lstm_{name}'] = model
                    loaded = True
                    print(f"✅ Loaded Keras model: {saved}")
                except Exception as e:
                    # Fallback: load legacy TensorFlow SavedModel and keep the loaded object
                    try:
                        tfs = tf.saved_model.load(str(saved))
                        # store under same key; callers must handle callable signatures if used
                        self.models[f'lstm_{name}'] = tfs
                        loaded = True
                        print(f"✅ Loaded TF SavedModel (legacy) for: {saved}")
                    except Exception as e2:
                        print(f"⚠️ Failed to load SavedModel {saved}: {e} / {e2}")

                # If the SavedModel directory contains a metadata/mapping file, load it.
                if loaded:
                    for fname in ('metadata.json', 'lstm_metadata.json', 'output_mapping.json', 'mapping.json'):
                        mp = saved / fname
                        if mp.exists():
                            try:
                                raw = json.loads(mp.read_text(encoding='utf-8'))
                                mapping = {}
                                # Accept formats: list of outputs, dict of target->index, or {'outputs': [...]}.
                                if isinstance(raw, list):
                                    for i, k in enumerate(raw):
                                        mapping[str(k)] = int(i)
                                elif isinstance(raw, dict):
                                    if 'outputs' in raw and isinstance(raw['outputs'], list):
                                        for i, k in enumerate(raw['outputs']):
                                            mapping[str(k)] = int(i)
                                    else:
                                        # assume target->index
                                        for k, v in raw.items():
                                            try:
                                                mapping[str(k)] = int(v)
                                            except Exception:
                                                # if values are string names, try reverse mapping
                                                pass
                                if mapping:
                                    self.lstm_mappings[name] = mapping
                                    print(f"✅ Loaded LSTM mapping for {name}: {mapping}")
                                    break
                            except Exception as me:
                                print(f"⚠️ Failed to load LSTM mapping {mp}: {me}")

            # Build a quick map of available scaler keys for lookup
            # keys in self.scalers are like 'calapan' or 'oriental_mindoro'
            self._scaler_keys = set(self.scalers.keys())
            
            if 'last_data' in self.models:
                self.last_data = self.models['last_data']
            
        except Exception as e:
            print(f"❌ Error loading models: {e}")
    
    def get_location_data(self, location_name):
        """Get weather data for a specific location"""
        if self.data is None:
            return None
        
        # Try exact match first
        location_data = self.data[self.data['municipality'].str.lower() == location_name.lower()]
        
        # If no exact match, try province match
        if location_data.empty:
            location_data = self.data[self.data['province'].str.lower() == location_name.lower()]
        
        # If still no match, try country match
        if location_data.empty:
            location_data = self.data[self.data['country'].str.lower() == location_name.lower()]
        
        if not location_data.empty:
            # Return the most recent data for the location
            return location_data.sort_values('date').iloc[-1]
        
        return None

    def _normalize_location_key(self, location_name: str) -> str:
        """Normalize a city/location name to the scaler/model key format.

        e.g., "Calapan City" -> "calapan_city" or "Calapan" -> "calapan"
        """
        if not location_name:
            return ''
        normalized = location_name.lower().replace(' ', '_')
        normalized = ''.join(ch for ch in normalized if (ch.isalnum() or ch == '_'))
        return normalized

    def _get_location_lstm(self, location_name: str):
        """Return a per-location LSTM model if available in self.models.

        Looks for keys like 'lstm_calapan'. Returns the model or None.
        """
        key = self._normalize_location_key(location_name)
        lookup = f'lstm_{key}'
        return self.models.get(lookup)
    
    def get_current_weather(self, city='Oriental Mindoro', save_to_db=True):
        """Get current weather using ML predictions based on last known data"""
        if self.last_data is None:
            # Fallback to CSV data
            location_data = self.get_location_data(city)
            if location_data is None:
                return None
        else:
            # Use last known data as base
            location_data = self.last_data
        
        # Add small random variations to simulate real-time
        temp_variation = np.random.uniform(-1, 1)
        humidity_variation = np.random.randint(-3, 3)
        
        current_weather = {
            'city': city,
            'country': 'Philippines',
            'latitude': 13.0,  # Approximate Philippines latitude
            'longitude': 122.0,  # Approximate Philippines longitude
            'temperature': round(location_data['temperature'] + temp_variation, 1),
            'feels_like': round(location_data['temperature'] + temp_variation + 2, 1),
            'description': location_data['condition'],
            'humidity': max(0, min(100, int(location_data['humidity']) + humidity_variation)),
            'windKmh': round(location_data['wind_speed'], 1),
            'windDirection': 'Variable',
            'windDegree': 0,
            'pressure': round(location_data['pressure'], 1),
            'visibilityKm': 10.0,
            'uvIndex': 6,
            'cloud': 50,
            'precipMm': round(location_data['rainfall'], 2),
            'icon': self._get_weather_icon(location_data['condition']),
            'iconUrl': None,
            'sunrise': '06:00 AM',
            'sunset': '06:00 PM',
            'moonPhase': 'Waxing Crescent',
            'moonIllumination': 45,
        }
        
        # Save to database if requested
        if save_to_db:
            self._save_weather_to_db(current_weather, 'current', datetime.now().date())
        
        return current_weather
    
    def predict_tomorrow(self, city='Oriental Mindoro', save_to_db=True):
        """Predict tomorrow's weather using ML models"""
        current = self.get_current_weather(city, save_to_db=False)
        if not current:
            return None
        
        # Use ML models to predict tomorrow's values (pass city so we can prefer per-location scalers)
        tomorrow_values = self._predict_next_day(location=city)
        
        tomorrow = {
            'date': (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'day': 'Tomorrow',
            'city': city,
            'country': 'Philippines',
            'latitude': current.get('latitude'),
            'longitude': current.get('longitude'),
            'temperature': round(tomorrow_values.get('temperature', current['temperature']), 1),
            'min': round(tomorrow_values.get('temperature', current['temperature']) - 2, 1),
            'max': round(tomorrow_values.get('temperature', current['temperature']) + 3, 1),
            'description': tomorrow_values.get('condition', current['description']),
            'humidity': max(40, min(95, tomorrow_values.get('humidity', current['humidity']))),
            'windKmh': max(0, round(tomorrow_values.get('wind_speed', current['windKmh']), 1)),
            'windDirection': 'Variable',
            'pressure': round(tomorrow_values.get('pressure', current['pressure']), 1),
            'visibilityKm': 10.0,
            'uvIndex': 6,
            'cloud': 50,
            'precipMm': max(0, round(tomorrow_values.get('rainfall', 0), 2)),
            'icon': self._get_weather_icon(tomorrow_values.get('condition', current['description'])),
        }
        
        # Save to database if requested
        if save_to_db:
            forecast_date = datetime.now().date() + timedelta(days=1)
            self._save_weather_to_db(tomorrow, 'tomorrow', forecast_date)
        
        return tomorrow
    
    def predict_weekly(self, city='Oriental Mindoro', days=7, save_to_db=True):
        """Predict weather for the next week using ML models"""
        current = self.get_current_weather(city, save_to_db=False)
        if not current:
            return []
        
        weekly_forecast = []
        current_values = {
            'temperature': current['temperature'],
            'humidity': current['humidity'],
            'rainfall': current['precipMm'],
            'wind_speed': current['windKmh'],
            'pressure': current['pressure'],
            'condition': current['description']
        }
        
        for i in range(1, days + 1):
            # Predict next day based on current
            next_values = self._predict_next_day_from_current(current_values)
            
            forecast_date = datetime.now() + timedelta(days=i)
            day_forecast = {
                'date': forecast_date.strftime('%Y-%m-%d'),
                'day': forecast_date.strftime('%A'),
                'city': city,
                'country': 'Philippines',
                'latitude': current.get('latitude'),
                'longitude': current.get('longitude'),
                'temperature': round(next_values.get('temperature', current_values['temperature']), 1),
                'min': round(next_values.get('temperature', current_values['temperature']) - 3, 1),
                'max': round(next_values.get('temperature', current_values['temperature']) + 4, 1),
                'description': next_values.get('condition', current_values['condition']),
                'humidity': max(40, min(95, next_values.get('humidity', current_values['humidity']))),
                'windKmh': max(0, round(next_values.get('wind_speed', current_values['wind_speed']), 1)),
                'windDirection': 'Variable',
                'pressure': round(next_values.get('pressure', current_values['pressure']), 1),
                'visibilityKm': 10.0,
                'uvIndex': max(0, min(11, 6 + np.random.randint(-2, 2))),
                'cloud': max(0, min(100, 50 + np.random.randint(-20, 20))),
                'precipMm': max(0, round(next_values.get('rainfall', 0), 2)),
                'icon': self._get_weather_icon(next_values.get('condition', current_values['condition'])),
            }
            weekly_forecast.append(day_forecast)
            
            # Update current values for next prediction
            current_values = next_values
            
            # Save to database if requested
            if save_to_db:
                self._save_weather_to_db(day_forecast, 'daily', forecast_date.date())
        
        return weekly_forecast
    
    def _predict_next_day(self, location=None):
        """Predict next day's weather using trained models"""
        predictions = {}
        
        # Predict numerical values
        numerical_cols = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']

        # Prefer per-location LSTM for temperature when available
        lstm_model = None
        if location is not None:
            lstm_model = self._get_location_lstm(location)
        if lstm_model is not None:
            try:
                last_temp = self._get_last_values('temperature', 7)
                if last_temp is not None:
                    X_seq = np.array(last_temp).reshape(1, -1, 1).astype(np.float32)
                    forecast = None
                    # Keras model
                    if hasattr(lstm_model, 'predict'):
                        pred = lstm_model.predict(X_seq)
                        arr = np.asarray(pred).ravel()
                        # Allow configurable mapping per LSTM
                        mapping = None
                        try:
                            mapping = self.lstm_mappings.get(self._normalize_location_key(location))
                        except Exception:
                            mapping = None
                        if arr.size >= 1:
                            # If mapping exists, use it to populate targets
                            if mapping:
                                for target, idx in mapping.items():
                                    try:
                                        i = int(idx)
                                        if i < arr.size:
                                            predictions[target] = max(0, float(arr[i]))
                                    except Exception:
                                        continue
                                # set primary temperature if present
                                if 'temperature' in predictions:
                                    forecast = float(predictions['temperature'])
                                else:
                                    forecast = float(arr[0])
                            else:
                                # default positional mapping
                                forecast = float(arr[0])
                                if arr.size >= 2:
                                    try:
                                        predictions['humidity'] = max(0, float(arr[1]))
                                    except Exception:
                                        pass
                                if arr.size >= 3:
                                    try:
                                        predictions['rainfall'] = max(0, float(arr[2]))
                                    except Exception:
                                        pass
                                if arr.size >= 4:
                                    try:
                                        predictions['wind_speed'] = max(0, float(arr[3]))
                                    except Exception:
                                        pass
                                if arr.size >= 5:
                                    try:
                                        predictions['pressure'] = max(0, float(arr[4]))
                                    except Exception:
                                        pass
                        else:
                            forecast = None
                    else:
                        # TF SavedModel fallback - try serving_default signature
                        sig = None
                        try:
                            sig = lstm_model.signatures.get('serving_default') if hasattr(lstm_model, 'signatures') else None
                        except Exception:
                            sig = None
                        if sig is not None:
                            try:
                                import tensorflow as _tf
                                t = _tf.constant(X_seq)
                                out = sig(t)
                                if isinstance(out, dict):
                                    first = list(out.values())[0]
                                else:
                                    first = out
                                arr = np.asarray(first.numpy()).ravel()
                                mapping = None
                                try:
                                    mapping = self.lstm_mappings.get(self._normalize_location_key(location))
                                except Exception:
                                    mapping = None
                                if arr.size >= 1:
                                    if mapping:
                                        for target, idx in mapping.items():
                                            try:
                                                i = int(idx)
                                                if i < arr.size:
                                                    predictions[target] = max(0, float(arr[i]))
                                            except Exception:
                                                continue
                                        if 'temperature' in predictions:
                                            forecast = float(predictions['temperature'])
                                        else:
                                            forecast = float(arr[0])
                                    else:
                                        forecast = float(arr[0])
                                        if arr.size >= 2:
                                            try:
                                                predictions['humidity'] = max(0, float(arr[1]))
                                            except Exception:
                                                pass
                                        if arr.size >= 3:
                                            try:
                                                predictions['rainfall'] = max(0, float(arr[2]))
                                            except Exception:
                                                pass
                                        if arr.size >= 4:
                                            try:
                                                predictions['wind_speed'] = max(0, float(arr[3]))
                                            except Exception:
                                                pass
                                        if arr.size >= 5:
                                            try:
                                                predictions['pressure'] = max(0, float(arr[4]))
                                            except Exception:
                                                pass
                                else:
                                    forecast = None
                            except Exception:
                                forecast = None
                    if forecast is not None:
                        predictions['temperature'] = max(0.0, forecast)
                        print(f"✅ Used per-location LSTM for {location} temperature prediction: {forecast}")
                    else:
                        print(f"⚠️ Per-location LSTM found for {location} but inference failed; falling back")
                else:
                    print(f"⚠️ Not enough history to use LSTM for {location}; falling back")
            except Exception as e:
                print(f"⚠️ Error using per-location LSTM for {location}: {e}")

        for col in numerical_cols:
            model_key = f'{col}_model'
            if model_key in self.models:
                model = self.models[model_key]
                try:
                    if hasattr(model, 'forecast'):
                        # ARIMA model
                        forecast = model.forecast(steps=1)[0]
                    else:
                        # Prepare last 7 values as features
                        last_values = self._get_last_values(col, 7)
                        if last_values is None:
                            # fallback to last_data
                            forecast = self.last_data.get(col, 25)
                        else:
                            X = np.array(last_values).reshape(1, -1)
                            # scale if scaler available for temperature; prefer per-location scaler if location provided
                            if col == 'temperature':
                                scaler_to_use = None
                                if location is not None:
                                    normalized = ''.join(ch for ch in location.lower().replace(' ', '_') if (ch.isalnum() or ch == '_'))
                                    if normalized in getattr(self, '_scaler_keys', set()):
                                        scaler_to_use = self.scalers.get(normalized)
                                if scaler_to_use is None and 'temperature' in self.scalers:
                                    scaler_to_use = self.scalers.get('temperature')
                                if scaler_to_use is not None:
                                    try:
                                        X = scaler_to_use.transform(X)
                                    except Exception:
                                        pass

                            # xgboost.Booster requires DMatrix
                            if isinstance(model, xgb.core.Booster):
                                dX = xgb.DMatrix(X)
                                preds = model.predict(dX)
                                forecast = float(preds[0])
                            else:
                                # sklearn-like estimator
                                preds = model.predict(X)
                                # model.predict may return array-like
                                forecast = float(np.asarray(preds).ravel()[0])

                    # If temperature already predicted by LSTM, keep that value
                    if col == 'temperature' and 'temperature' in predictions:
                        # keep LSTM result
                        pass
                    else:
                        predictions[col] = max(0, forecast)
                except Exception as e:
                    print(f'⚠️ Prediction error for {col}: {e}')
                    predictions[col] = self.last_data.get(col, 25)
            else:
                predictions[col] = self.last_data.get(col, 25)
        
        # Predict condition
        if 'condition_model' in self.models and 'condition_encoder' in self.models:
            model = self.models['condition_model']
            encoder = self.models['condition_encoder']
            try:
                # Use last 3 conditions as features
                last_conditions = self._get_last_conditions(3)
                if last_conditions is not None:
                    pred_encoded = model.predict([last_conditions])[0]
                    pred_encoded = max(0, min(len(encoder.classes_) - 1, int(round(pred_encoded))))
                    predictions['condition'] = encoder.inverse_transform([pred_encoded])[0]
                else:
                    predictions['condition'] = self.last_data.get('condition', 'Sunny')
            except:
                predictions['condition'] = self.last_data.get('condition', 'Sunny')
        else:
            predictions['condition'] = self.last_data.get('condition', 'Sunny')
        
        return predictions
    
    def _predict_next_day_from_current(self, current_values):
        """Predict next day from current values (simplified)"""
        # Simple trend-based prediction
        predictions = {}
        
        # Temperature: slight random change
        predictions['temperature'] = current_values['temperature'] + np.random.uniform(-2, 2)
        
        # Humidity: slight change
        predictions['humidity'] = max(30, min(100, current_values['humidity'] + np.random.randint(-10, 10)))
        
        # Rainfall: random small amount
        predictions['rainfall'] = max(0, np.random.uniform(0, 5))
        
        # Wind speed: slight change
        predictions['wind_speed'] = max(0, current_values['wind_speed'] + np.random.uniform(-3, 3))
        
        # Pressure: slight change
        predictions['pressure'] = current_values['pressure'] + np.random.uniform(-5, 5)
        
        # Condition: simple transition
        predictions['condition'] = self._predict_next_condition(current_values['condition'])
        
        return predictions
    
    def _get_last_values(self, column, n_days):
        """Get last n values for a column"""
        if self.data is None or column not in self.data.columns:
            return None
        
        # Get daily averages
        daily_data = self.data.groupby('date')[column].mean().reset_index()
        daily_data = daily_data.sort_values('date')
        
        if len(daily_data) < n_days:
            return None
        
        return daily_data[column].iloc[-n_days:].values
    
    def _get_last_conditions(self, n_days):
        """Get last n condition encodings"""
        if self.data is None or 'condition_encoder' not in self.models:
            return None
        
        encoder = self.models['condition_encoder']
        
        # Get daily mode conditions
        daily_conditions = self.data.groupby('date')['weather_condition'].agg(
            lambda x: x.mode().iloc[0] if not x.mode().empty else 'Sunny'
        ).reset_index()
        daily_conditions = daily_conditions.sort_values('date')
        
        if len(daily_conditions) < n_days:
            return None
        
        last_conditions = daily_conditions['weather_condition'].iloc[-n_days:].values
        encoded = encoder.transform(last_conditions)
        
        return encoded
    
    def _predict_next_condition(self, current_condition):
        """Predict next day's weather condition based on current"""
        current_lower = current_condition.lower()
        
        # Weather transition probabilities (simplified model)
        if 'sunny' in current_lower or 'clear' in current_lower:
            options = ['Sunny', 'Partly cloudy', 'Partly cloudy', 'Cloudy']
            weights = [0.5, 0.3, 0.15, 0.05]
        elif 'partly' in current_lower or 'patchy' in current_lower:
            options = ['Partly cloudy', 'Sunny', 'Cloudy', 'Light rain']
            weights = [0.4, 0.3, 0.2, 0.1]
        elif 'cloudy' in current_lower or 'overcast' in current_lower:
            options = ['Cloudy', 'Partly cloudy', 'Light rain', 'Rainy']
            weights = [0.35, 0.35, 0.2, 0.1]
        elif 'rain' in current_lower or 'drizzle' in current_lower:
            options = ['Light rain', 'Cloudy', 'Partly cloudy', 'Sunny']
            weights = [0.35, 0.35, 0.2, 0.1]
        elif 'thunder' in current_lower or 'storm' in current_lower:
            options = ['Rainy', 'Light rain', 'Cloudy', 'Partly cloudy']
            weights = [0.4, 0.3, 0.2, 0.1]
        else:
            options = ['Partly cloudy', 'Sunny', 'Cloudy', 'Light rain']
            weights = [0.35, 0.3, 0.25, 0.1]
        
        return np.random.choice(options, p=weights)
    
    def _get_weather_icon(self, condition):
        """Map weather condition to icon code"""
        condition_lower = condition.lower()
        
        if 'clear' in condition_lower or 'sunny' in condition_lower:
            return '01d'
        elif 'partly' in condition_lower or 'patchy' in condition_lower:
            return '02d'
        elif 'cloudy' in condition_lower or 'overcast' in condition_lower:
            return '03d'
        elif 'thunder' in condition_lower or 'storm' in condition_lower:
            return '11d'
        elif 'rain' in condition_lower or 'drizzle' in condition_lower:
            return '10d'
        elif 'snow' in condition_lower:
            return '13d'
        elif 'mist' in condition_lower or 'fog' in condition_lower:
            return '50d'
        else:
            return '02d'  # Default to partly cloudy
    
    def get_weather_impact_for_shrimp(self, weather_data):
        """Analyze weather impact on shrimp farming"""
        if not weather_data:
            return None
        
        impacts = {
            'temperature_impact': 'normal',
            'rain_impact': 'normal',
            'wind_impact': 'normal',
            'recommendations': []
        }
        
        # Temperature impact
        temp = weather_data.get('temperature', 26)
        if temp > 32:
            impacts['temperature_impact'] = 'high_risk'
            impacts['recommendations'].append('⚠️ High temperature alert: Increase aeration, monitor oxygen levels closely')
        elif temp > 28:
            impacts['temperature_impact'] = 'moderate_risk'
            impacts['recommendations'].append('Elevated temperature: Ensure adequate water circulation')
        elif temp < 20:
            impacts['temperature_impact'] = 'moderate_risk'
            impacts['recommendations'].append('Low temperature: Reduce feeding, shrimp metabolism is slower')
        else:
            impacts['temperature_impact'] = 'optimal'
        
        # Rain impact
        precip = weather_data.get('precipMm', 0)
        if precip > 20:
            impacts['rain_impact'] = 'high_risk'
            impacts['recommendations'].append('🌧️ Heavy rain expected: Monitor salinity and pH, reduce feeding')
        elif precip > 5:
            impacts['rain_impact'] = 'moderate_risk'
            impacts['recommendations'].append('Moderate rain: Check water quality after rainfall')
        
        # Wind impact
        wind = weather_data.get('windKmh', 10)
        if wind > 40:
            impacts['wind_impact'] = 'high_risk'
            impacts['recommendations'].append('💨 Strong winds: Secure equipment, monitor water turbidity')
        elif wind > 25:
            impacts['wind_impact'] = 'moderate_risk'
            impacts['recommendations'].append('Moderate winds: Good for natural aeration')
        else:
            impacts['wind_impact'] = 'optimal'
            impacts['recommendations'].append('✅ Good wind conditions for natural aeration')
        
        # UV Index impact
        uv = weather_data.get('uvIndex', 5)
        if uv > 8:
            impacts['recommendations'].append('High UV index: Consider shade nets to reduce heat stress')
        
        return impacts

    def _save_weather_to_db(self, weather_data, forecast_type, forecast_date):
        """Save weather forecast to database"""
        try:
            from api.models import WeatherForecast
            from django.utils import timezone
            
            # Prepare data for database
            weather_obj, created = WeatherForecast.objects.update_or_create(
                city=weather_data.get('city', 'Unknown'),
                forecast_date=forecast_date,
                forecast_type=forecast_type,
                defaults={
                    'country': weather_data.get('country', ''),
                    'latitude': weather_data.get('latitude'),
                    'longitude': weather_data.get('longitude'),
                    'temperature': weather_data.get('temperature') or weather_data.get('max', 25),
                    'feels_like': weather_data.get('feels_like'),
                    'min_temperature': weather_data.get('min'),
                    'max_temperature': weather_data.get('max'),
                    'condition': weather_data.get('description', 'Unknown'),
                    'humidity': weather_data.get('humidity', 70),
                    'pressure': weather_data.get('pressure', 1010),
                    'cloud_cover': weather_data.get('cloud', 50),
                    'wind_speed': weather_data.get('windKmh', 10),
                    'wind_direction': weather_data.get('windDirection', ''),
                    'wind_degree': weather_data.get('windDegree'),
                    'gust_speed': weather_data.get('gustKmh'),
                    'precipitation': weather_data.get('precipMm', 0),
                    'visibility': weather_data.get('visibilityKm', 10),
                    'uv_index': weather_data.get('uvIndex', 5),
                    'sunrise': weather_data.get('sunrise', ''),
                    'sunset': weather_data.get('sunset', ''),
                    'moon_phase': weather_data.get('moonPhase', ''),
                    'moon_illumination': weather_data.get('moonIllumination'),
                    'weather_icon': weather_data.get('icon', '02d'),
                    'source': 'ml_prediction',
                }
            )
            
            # Calculate and save impact assessments
            weather_obj.calculate_impacts()
            weather_obj.save()
            
            return weather_obj
            
        except Exception as e:
            print(f"⚠️ Error saving weather to database: {e}")
            return None

# DEPRECATED: No longer instantiated at module level.
# Instantiate manually if needed for testing:
#   wp = WeatherPredictor()
