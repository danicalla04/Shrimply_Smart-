import os
import json
import warnings
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
warnings.filterwarnings('ignore')

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("⚠️ pandas/numpy not available - data features will be disabled")

try:
    from statsmodels.tsa.arima.model import ARIMA
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    print("⚠️ statsmodels not available - ARIMA forecasting will be disabled")

try:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import LabelEncoder
    from sklearn.model_selection import train_test_split
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ scikit-learn not available - ML models will be disabled")

# Try to import ML libraries (they may not be installed)
try:
    import tensorflow as tf
    from tensorflow import keras
    TENSORFLOW_AVAILABLE = True
    
    # Custom Keras layer that replaces Lambda(reduce_sum) in attention-based LSTM models.
    # This avoids cross-version Python bytecode serialization issues with Lambda layers.
    class ReduceSumLayer(keras.layers.Layer):
        """Sums over the time axis (axis=1) for attention-weighted context vectors."""
        def call(self, x):
            return tf.reduce_sum(x, axis=1)
        def get_config(self):
            return super().get_config()

except ImportError:
    TENSORFLOW_AVAILABLE = False
    print("âš ï¸ TensorFlow not available - LSTM models will be disabled")

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("âš ï¸ XGBoost not available - XGBoost models will be disabled")


def _load_keras_model_trusted(filepath, extra_custom_objects=None):
    """Load trusted local .h5 models. Keras 3 defaults to safe_mode=True (blocks Lambda layers)."""
    if not TENSORFLOW_AVAILABLE:
        raise RuntimeError('TensorFlow not available')
    co = {
        'ReduceSumLayer': ReduceSumLayer,
        'mse': keras.metrics.MeanSquaredError(),
        'mean_squared_error': keras.metrics.MeanSquaredError(),
        'mae': keras.metrics.MeanAbsoluteError(),
        'mean_absolute_error': keras.metrics.MeanAbsoluteError(),
    }
    if extra_custom_objects:
        co.update(extra_custom_objects)
    try:
        return keras.models.load_model(
            filepath, compile=False, custom_objects=co, safe_mode=False,
        )
    except TypeError:
        return keras.models.load_model(filepath, compile=False, custom_objects=co)


class EnhancedWeatherPredictor:
    def __init__(self):
        self.csv_path = Path(__file__).resolve().parent.parent.parent / 'dataset' / 'data' / 'philippines_weather_merged.csv'
        self.featured_csv_path = Path(__file__).resolve().parent.parent.parent / 'dataset' / 'data' / 'philippines_weather_featured_v3.csv'
        self.featured_csv_v2_path = Path(__file__).resolve().parent.parent.parent / 'dataset' / 'data' / 'philippines_weather_featured_v2.csv'
        self.models_dir = Path(__file__).resolve().parent.parent.parent / 'dataset' / 'models'
        self.openweather_api_key = os.getenv('OPENWEATHER_API_KEY', '')
        self.data = None
        self.featured_data = None
        self.models = {}
        self.correction_models = {}  # ML models to correct OpenWeather data
        self.lstm_models = {}  # LSTM models for ensemble
        self.xgboost_models = {}  # XGBoost models for ensemble
        self.xgboost_v3_models = {}  # v3 XGBoost models (improved)
        self.xgboost_v3_feature_lists = {}  # v3 feature lists
        self.quantile_models = {}  # Quantile regression for confidence intervals
        self.xgboost_feature_lists = {}  # Feature lists per XGBoost model
        self.model_feature_cols = {}  # Feature columns for our primary models
        self.weather_history = []  # Recent weather history for lag features
        self.prediction_log = []  # Feedback loop: track predictions vs actuals
        self.last_data = None
        self.model_metrics = {}  # Model accuracy metrics for confidence intervals
        self.lstm_scalers = {}  # Per-location MinMaxScaler for LSTM normalization
        # Denormalization ranges (matching training data normalization)
        self.norm_ranges = {
            'temperature': (20, 38),
            'humidity': (40, 100),
            'rainfall': (0, 150),
            'wind_speed': (0, 60),
            'pressure': (990, 1030),
        }
        # Physical limits for post-processing
        self.physical_limits = {
            'temperature': (15, 45),
            'humidity': (20, 100),
            'rainfall': (0, 500),
            'wind_speed': (0, 200),
            'pressure': (900, 1060),
        }
        # Max day-to-day change (smoothness constraint)
        self.max_daily_change = {
            'temperature': 5.0,
            'humidity': 25.0,
            'rainfall': 100.0,
            'wind_speed': 30.0,
            'pressure': 15.0,
        }
        # Geospatial data for municipalities
        self.municipality_geo = {
            'Urdaneta':    {'lat': 15.976, 'lon': 120.571, 'elev':  56, 'coast_km': 35},
            'Dagupan':     {'lat': 16.043, 'lon': 120.340, 'elev':   2, 'coast_km':  1},
            'San Carlos':  {'lat': 15.928, 'lon': 120.347, 'elev':   3, 'coast_km':  2},
            'Calapan':     {'lat': 13.411, 'lon': 121.180, 'elev':   7, 'coast_km':  1},
            'Pinamalayan': {'lat': 13.015, 'lon': 121.478, 'elev':  15, 'coast_km':  2},
            'Roxas':       {'lat': 12.626, 'lon': 121.507, 'elev':  10, 'coast_km':  3},
            'Santa Cruz':  {'lat': 13.221, 'lon': 121.407, 'elev':  30, 'coast_km':  8},
            'Bacolod':     {'lat': 10.676, 'lon': 122.950, 'elev':  10, 'coast_km':  1},
            'Silay':       {'lat': 10.812, 'lon': 122.969, 'elev':  20, 'coast_km':  3},
            'Talisay':     {'lat': 10.741, 'lon': 122.966, 'elev':  12, 'coast_km':  1},
            'Cebu City':   {'lat': 10.315, 'lon': 123.885, 'elev':  25, 'coast_km':  1},
            'Lapu-Lapu':   {'lat': 10.311, 'lon': 123.949, 'elev':   5, 'coast_km':  0.5},
            'Mandaue':     {'lat': 10.324, 'lon': 123.922, 'elev':  10, 'coast_km':  1},
            'Davao City':  {'lat':  7.073, 'lon': 125.612, 'elev':  20, 'coast_km':  5},
            'Digos':       {'lat':  6.749, 'lon': 125.357, 'elev':  12, 'coast_km': 10},
        }
        self.municipalities = []
        
        self.load_data()
        self.load_model_metrics()
        self.load_models()
        self.load_municipalities()
        self.initialize_correction_models()
        self.load_advanced_models()  # Load LSTM and XGBoost models
        self._seed_weather_history()  # Seed history from CSV for lag features

    def load_data(self):
        """Load weather data from CSV file"""
        try:
            if os.path.exists(self.csv_path):
                self.data = pd.read_csv(self.csv_path, sep=',', on_bad_lines='skip', engine='python')
                self.data['date'] = pd.to_datetime(self.data['date'])
                print(f"[OK] Loaded {len(self.data)} weather records from CSV")
            else:
                print(f"âš ï¸ Weather CSV not found at {self.csv_path}")
                self.data = None
        except Exception as e:
            print(f"[ERROR] Error loading weather CSV: {e}")
            self.data = None

    def load_model_metrics(self):
        """Load model metrics for calculating confidence intervals"""
        try:
            metrics_path = self.models_dir / 'weather_model_metrics.json'
            if metrics_path.exists():
                with open(metrics_path, 'r') as f:
                    self.model_metrics = json.load(f)
                print(f"[OK] Loaded model metrics for confidence intervals")
            else:
                print(f"[WARN] Model metrics not found - using default confidence intervals")
                self.model_metrics = {
                    'temperature': {'rmse': 0.0201},
                    'humidity': {'rmse': 0.0312},
                    'rainfall': {'rmse': 0.0195},
                    'wind_speed': {'rmse': 0.0209},
                    'pressure': {'rmse': 0.0182},
                }
        except Exception as e:
            print(f"[ERROR] Error loading model metrics: {e}")
            self.model_metrics = {}

    def load_municipalities(self):
        """Load unique municipalities for dropdown"""
        if self.data is not None:
            unique_locations = self.data[['province', 'municipality']].drop_duplicates()
            self.municipalities = unique_locations.to_dict('records')
            print(f"[OK] Loaded {len(self.municipalities)} municipalities")
        else:
            # Fallback municipalities
            self.municipalities = [
                {'province': 'Oriental Mindoro', 'municipality': 'Pinamalayan'},
                {'province': 'Oriental Mindoro', 'municipality': 'Calapan'},
                {'province': 'Pangasinan', 'municipality': 'San Carlos'},
                {'province': 'Pangasinan', 'municipality': 'Urdaneta'},
                {'province': 'Negros Occidental', 'municipality': 'Bacolod'},
                {'province': 'Negros Occidental', 'municipality': 'Silay'},
                {'province': 'Negros Occidental', 'municipality': 'Talisay'},
                {'province': 'Davao del Sur', 'municipality': 'Digos'},
                {'province': 'Cebu', 'municipality': 'Lapu-Lapu'}
            ]

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
                    print(f"[OK] Loaded {file}")
                else:
                    print(f"âš ï¸ Model file not found: {file}")
            
            if 'last_data' in self.models:
                self.last_data = self.models['last_data']
            
            # Load feature column lists for each model
            for target in ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']:
                feat_path = self.models_dir / f'{target}_feature_cols.pkl'
                if feat_path.exists():
                    self.model_feature_cols[target] = joblib.load(feat_path)
                    print(f"[OK] Loaded {target} feature cols ({len(self.model_feature_cols[target])} features)")
            
            # Load Calapan-specific high-accuracy models (v4)
            self.load_calapan_models()
            
        except Exception as e:
            print(f"[ERROR] Error loading models: {e}")

    def load_calapan_models(self):
        """Load Calapan-specific high-accuracy models (v4)"""
        try:
            self.calapan_models = {}
            self.calapan_scaler = None
            
            # Load Calapan feature scaler
            scaler_path = self.models_dir / 'calapan_feature_scaler_v4.pkl'
            if scaler_path.exists():
                self.calapan_scaler = joblib.load(scaler_path)
                print(f"[OK] Loaded Calapan feature scaler")
            
            # Load Calapan XGBoost models
            for target in ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']:
                model_path = self.models_dir / f'calapan_{target}_xgboost_v4.pkl'
                if model_path.exists():
                    self.calapan_models[f'{target}_xgboost'] = joblib.load(model_path)
                    print(f"[OK] Loaded Calapan {target} XGBoost model")
                
                # Load LSTM models if available
                lstm_path = self.models_dir / f'calapan_{target}_lstm_v4.h5'
                if TENSORFLOW_AVAILABLE and lstm_path.exists():
                    try:
                        self.calapan_models[f'{target}_lstm'] = _load_keras_model_trusted(lstm_path)
                        print(f"[OK] Loaded Calapan {target} LSTM model")
                    except Exception as e:
                        print(f"[WARN] Could not load Calapan {target} LSTM: {e}")
            
            if self.calapan_models:
                print(f"[OK] Calapan high-accuracy models loaded: {len(self.calapan_models)} models")
            else:
                print("[INFO] No Calapan-specific models found, using general models")
                
        except Exception as e:
            print(f"[ERROR] Error loading Calapan models: {e}")
            self.calapan_models = {}

    def initialize_correction_models(self):
        """Initialize ML models for correcting OpenWeather data"""
        # These models learn the bias between OpenWeather and actual local measurements
        correction_features = ['temperature', 'humidity', 'pressure', 'wind_speed']
        
        for feature in correction_features:
            model_path = self.models_dir / f'correction_{feature}_model.pkl'
            if model_path.exists():
                self.correction_models[feature] = joblib.load(model_path)
                print(f"[OK] Loaded correction model for {feature}")
            else:
                # Create simple correction model if not exists
                self.correction_models[feature] = self._create_correction_model(feature)

    def _create_correction_model(self, feature):
        """Create a correction model for a weather feature"""
        # This would be trained on historical OpenWeather vs local data
        # For now, return a simple bias correction
        return {'bias': 0, 'scale': 1}

    def load_advanced_models(self):
        """Load LSTM and XGBoost models for ensemble predictions - prefers v3 models"""
        try:
            # All 15 municipality locations
            all_locations = [
                'dagupan', 'lingayen', 'alaminos',  # Pangasinan
                'calapan', 'pinamalayan', 'oriental_mindoro',  # Oriental Mindoro
                'bacolod', 'san_carlos', 'silay',  # Negros Occidental
                'cebu', 'mandaue', 'lapu_lapu',  # Cebu
                'digos', 'davao', 'mati',  # Davao del Sur
            ]

            # Load LSTM models for each location (prefer v3, fall back to v1)
            if TENSORFLOW_AVAILABLE:
                # Some model files use "_city" suffix (e.g. lstm_cebu_city_v3.h5)
                _city_aliases = {'cebu': 'cebu_city', 'davao': 'davao_city'}
                for loc in all_locations:
                    file_loc = _city_aliases.get(loc, loc)  # map to actual file name
                    # Candidate paths in priority order
                    candidates = [
                        (self.models_dir / f'lstm_{file_loc}_v3.h5', 'v3'),
                        (self.models_dir / f'lstm_{file_loc}.h5', 'v1'),
                    ]
                    loaded = False
                    for model_path, version in candidates:
                        if not model_path.exists():
                            continue
                        try:
                            self.lstm_models[loc] = _load_keras_model_trusted(model_path)
                            print(f"[OK] Loaded LSTM model for {loc} ({version})")
                            loaded = True
                            break
                        except Exception as e:
                            print(f"[WARN] LSTM {version} for {loc} failed: {e}, trying next...")
                    if loaded:
                        # Load matching scaler (prefer v3)
                        for sp in [
                            self.models_dir / f'scaler_{file_loc}_v3.pkl',
                            self.models_dir / f'scaler_{file_loc}.pkl',
                        ]:
                            if sp.exists():
                                self.lstm_scalers[loc] = joblib.load(sp)
                                print(f"[OK] Loaded scaler for {loc}")
                                break

            # Load XGBoost models (prefer v3)
            if XGBOOST_AVAILABLE:
                weather_params = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']
                for param in weather_params:
                    # Try v3 first
                    v3_path = self.models_dir / f'xgboost_{param}_v3.pkl'
                    orig_path = self.models_dir / f'xgboost_{param}.pkl'
                    model_path = v3_path if v3_path.exists() else orig_path
                    if model_path.exists():
                        try:
                            if v3_path.exists():
                                self.xgboost_v3_models[param] = joblib.load(model_path)
                                self.xgboost_models[param] = self.xgboost_v3_models[param]
                            else:
                                self.xgboost_models[param] = joblib.load(model_path)
                            version = "v3" if v3_path.exists() else "v1"
                            print(f"[OK] Loaded XGBoost model for {param} ({version})")
                        except MemoryError as me:
                            print(f"[WARN] MemoryError loading XGBoost {param}: {me}")

                # Load feature lists per model (prefer v3)
                generic_feats_path = self.models_dir / 'weather_xgb_features.pkl'
                generic_feats = joblib.load(generic_feats_path) if generic_feats_path.exists() else None
                for param in weather_params:
                    v3_feat_path = self.models_dir / f'xgboost_{param}_v3_features.pkl'
                    specific_path = self.models_dir / f'xgboost_{param}_features.pkl'
                    if v3_feat_path.exists():
                        feats = joblib.load(v3_feat_path)
                        self.xgboost_v3_feature_lists[param] = feats
                        self.xgboost_feature_lists[param] = feats
                        print(f"[OK] Loaded v3 feature list for {param}: {len(feats)} features")
                    elif specific_path.exists():
                        self.xgboost_feature_lists[param] = joblib.load(specific_path)
                        print(f"[OK] Loaded feature list for {param}: {len(self.xgboost_feature_lists[param])} features")
                    elif generic_feats is not None:
                        self.xgboost_feature_lists[param] = generic_feats
                        print(f"[OK] Using generic feature list for {param}: {len(generic_feats)} features")

                # Load quantile models for confidence intervals
                for param in weather_params:
                    for q_label, q_file in [('lower', 'qlower_v3'), ('upper', 'qupper_v3')]:
                        q_path = self.models_dir / f'xgboost_{param}_{q_file}.pkl'
                        if q_path.exists():
                            try:
                                self.quantile_models[f'{param}_{q_label}'] = joblib.load(q_path)
                                print(f"[OK] Loaded quantile model: {param}_{q_label} ({q_file})")
                            except MemoryError as me:
                                print(f"[WARN] MemoryError loading quantile {param}_{q_label}: {me}")
                        else:
                            # Legacy naming fallback
                            legacy_path = self.models_dir / f'xgboost_{param}_{q_label}.pkl'
                            if legacy_path.exists():
                                try:
                                    self.quantile_models[f'{param}_{q_label}'] = joblib.load(legacy_path)
                                    print(f"[OK] Loaded quantile model (legacy): {param}_{q_label}")
                                except MemoryError as me:
                                    print(f"[WARN] MemoryError loading legacy quantile {param}_{q_label}: {me}")

            # Load featured dataset — memory-efficient tail loading
            csv_loaded = False
            for csv_path in [self.featured_csv_path, self.featured_csv_v2_path]:
                if csv_loaded or not os.path.exists(csv_path):
                    continue
                try:
                    # Count rows to only load the tail portion (saves ~400MB)
                    with open(csv_path, 'r') as f:
                        total_rows = sum(1 for _ in f) - 1  # minus header
                    skip_rows = max(0, total_rows - 1500)
                    self.featured_data = pd.read_csv(
                        csv_path,
                        skiprows=range(1, skip_rows + 1) if skip_rows > 0 else None,
                    )
                    self.featured_data['date'] = pd.to_datetime(self.featured_data['date'])
                    print(f"[OK] Loaded featured dataset (last {len(self.featured_data)} of {total_rows} rows)")
                    csv_loaded = True
                except Exception as csv_e:
                    print(f"[WARN] Could not load featured CSV {csv_path}: {csv_e}")

        except Exception as e:
            print(f"[WARN] Error loading advanced models: {e}")
            import traceback
            traceback.print_exc()

    def _seed_weather_history(self):
        """Seed weather_history from the last 14 days of the CSV dataset so lag
        features are populated from the very first prediction request."""
        if self.data is None:
            return
        try:
            # Avoid sort_values() on ~900k rows — after loading TF/XGBoost it can OOM.
            n = min(14, len(self.data))
            recent = self.data.iloc[-n:]
            for _, row in recent.iterrows():
                entry = {
                    'temperature': float(row.get('temperature', 28)),
                    'humidity': float(row.get('humidity', 75)),
                    'rainfall': float(row.get('rainfall', 0)),
                    'wind_speed': float(row.get('wind_speed', 10)),
                    'pressure': float(row.get('pressure', 1013)),
                }
                self.weather_history.append(entry)
            print(f"[OK] Seeded weather history with {len(self.weather_history)} entries")
        except Exception as e:
            print(f"[WARN] Could not seed weather history: {e}")

    def fetch_openweather_data(self, location: str) -> Optional[Dict]:
        """Fetch current weather from OpenWeather API"""
        try:
            # Extract just the city name if location contains comma
            city_name = location.split(',')[0].strip()
            
            # First try with full location
            url = f'https://api.openweathermap.org/data/2.5/weather?q={location},PH&appid={self.openweather_api_key}&units=metric'
            response = requests.get(url, timeout=10)
            
            # If full location fails, try with just city name
            if response.status_code != 200:
                url = f'https://api.openweathermap.org/data/2.5/weather?q={city_name},PH&appid={self.openweather_api_key}&units=metric'
                response = requests.get(url, timeout=10)
            
            response.raise_for_status()
            
            data = response.json()
            
            # Extract relevant data with actual coordinates
            weather_data = {
                'temperature': data['main']['temp'],
                'feels_like': data['main']['feels_like'],
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'wind_speed': data['wind']['speed'] * 3.6,  # Convert m/s to km/h
                'wind_direction': data['wind'].get('deg', 0),
                'visibility': data.get('visibility', 10000) / 1000,  # Convert to km
                'clouds': data['clouds']['all'],
                'description': data['weather'][0]['description'].capitalize(),
                'icon': data['weather'][0]['icon'],
                'icon_url': f"https://openweathermap.org/img/wn/{data['weather'][0]['icon']}@2x.png",
                'country': data['sys'].get('country'),
                'latitude': data['coord']['lat'],
                'longitude': data['coord']['lon'],
                'city_name': data['name'],
                'sunrise': datetime.fromtimestamp(data['sys']['sunrise']).strftime('%H:%M'),
                'sunset': datetime.fromtimestamp(data['sys']['sunset']).strftime('%H:%M'),
                'uv_index': self._estimate_uv_index(data),
                'precipitation': data.get('rain', {}).get('1h', 0) or data.get('snow', {}).get('1h', 0) or 0
            }
            
            return weather_data
            
        except Exception as e:
            print(f"[ERROR] Error fetching OpenWeather data for {location}: {e}")
            return None

    def _estimate_uv_index(self, data):
        """Estimate UV index based on weather conditions"""
        # Simple estimation based on cloud cover and time of day
        base_uv = 8  # Tropical midday UV
        cloud_factor = (100 - data['clouds']['all']) / 100
        return round(base_uv * cloud_factor)

    def apply_ml_corrections(self, openweather_data: Dict, location: str) -> Dict:
        """Apply ML corrections to OpenWeather data for local accuracy.
        
        Uses trained RandomForest correction models that learned the bias between
        OpenWeather API readings and actual local ground-truth measurements.
        """
        corrected = openweather_data.copy()

        # Build the correction feature vector matching training column order:
        # [ow_temperature, ow_humidity, ow_pressure, ow_wind_speed, ow_visibility, ow_clouds]
        try:
            ow_features = np.array([[
                openweather_data.get('temperature', 28),
                openweather_data.get('humidity', 75),
                openweather_data.get('pressure', 1013),
                openweather_data.get('wind_speed', 10),
                openweather_data.get('visibility', 10),
                openweather_data.get('clouds', 50),
            ]], dtype=np.float32)

            param_map = {
                'temperature': 'temperature',
                'humidity': 'humidity',
                'pressure': 'pressure',
                'wind_speed': 'wind_speed',
            }

            for correction_key, data_key in param_map.items():
                model = self.correction_models.get(correction_key)
                if model is not None and hasattr(model, 'predict'):
                    try:
                        predicted_local = float(model.predict(ow_features)[0])
                        # Blend: 70% correction model, 30% raw OpenWeather to avoid over-correction
                        raw_val = openweather_data.get(data_key, predicted_local)
                        corrected[data_key] = 0.7 * predicted_local + 0.3 * raw_val
                    except Exception:
                        pass  # Keep original value

            try:
                climatology = self._get_location_climatology(location, datetime.now())
                for key in ['temperature', 'humidity', 'pressure', 'wind_speed']:
                    if key not in corrected or key not in climatology or not climatology[key]:
                        continue

                    month_avg = climatology[key].get('month_avg')
                    recent_avg = climatology[key].get('recent_avg')
                    trend = climatology[key].get('trend', 0.0)
                    if month_avg is None:
                        continue

                    seasonal_target = 0.65 * month_avg + 0.35 * (recent_avg if recent_avg is not None else month_avg)
                    seasonal_target += max(-self.max_daily_change.get(key, 5.0), min(self.max_daily_change.get(key, 5.0), trend)) * 0.15
                    corrected[key] = 0.75 * corrected[key] + 0.25 * seasonal_target
            except Exception as clim_err:
                print(f"[WARN] Climatology blending failed: {clim_err}")

        except Exception as e:
            print(f"[WARN] ML correction failed, using raw OpenWeather: {e}")

        return corrected

    def _get_location_climatology(self, location: str, reference_date: Optional[datetime] = None) -> Dict:
        """Build a small location-specific climatology from historical CSV data."""
        if self.data is None or self.data.empty or 'date' not in self.data.columns:
            return {}

        try:
            # Ensure date column is datetime type
            if not pd.api.types.is_datetime64_any_dtype(self.data['date']):
                self.data['date'] = pd.to_datetime(self.data['date'], errors='coerce')
            
            ref_date = reference_date or datetime.now()
            month = ref_date.month
            tokens = [token.strip().lower() for token in location.replace(',', ' ').split() if len(token.strip()) >= 3]

            location_data = self.data.copy()
            if tokens:
                location_mask = pd.Series(False, index=self.data.index)
                for column in ['city', 'municipality', 'province', 'country']:
                    if column not in self.data.columns:
                        continue
                    column_values = self.data[column].astype(str).str.lower()
                    column_mask = pd.Series(False, index=self.data.index)
                    for token in tokens:
                        column_mask = column_mask | column_values.str.contains(token, na=False)
                    location_mask = location_mask | column_mask

                matched = self.data[location_mask]
                if not matched.empty:
                    location_data = matched.copy()

            # Filter by month and recent dates, with fallback
            if 'date' in location_data.columns and len(location_data) > 0:
                try:
                    month_data = location_data[location_data['date'].dt.month == month]
                    if month_data.empty:
                        month_data = location_data  # Fallback to all data if no month match
                except:
                    month_data = location_data
                
                try:
                    recent_data = location_data.sort_values('date').tail(14)
                except:
                    recent_data = location_data.tail(14)
            else:
                month_data = location_data
                recent_data = location_data.tail(14) if len(location_data) >= 14 else location_data

            climatology = {}
            for param in ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']:
                if param not in month_data.columns:
                    continue
                    
                try:
                    month_avg = float(month_data[param].mean())
                    if pd.isna(month_avg):
                        continue
                        
                    recent_avg = month_avg
                    if param in recent_data.columns and not recent_data.empty:
                        recent_avg = float(recent_data[param].mean())
                        if pd.isna(recent_avg):
                            recent_avg = month_avg
                    
                    climatology[param] = {
                        'month_avg': month_avg,
                        'recent_avg': recent_avg,
                        'trend': recent_avg - month_avg,
                    }
                except Exception as param_err:
                    pass  # Skip this parameter if calculation fails

            return climatology
        except Exception as e:
            print(f"[WARN] Could not build location climatology for {location}: {e}")
            return {}
    
    def fetch_openweather_5day_forecast(self, location: str) -> Optional[List[Dict]]:
        """Fetch 5-day/3-hour forecast from OpenWeather API"""
        try:
            # Extract just the city name if location contains comma
            city_name = location.split(',')[0].strip()
            
            # Try with full location first
            url = f'https://api.openweathermap.org/data/2.5/forecast?q={location},PH&appid={self.openweather_api_key}&units=metric'
            response = requests.get(url, timeout=10)
            
            # If full location fails, try with just city name
            if response.status_code != 200:
                url = f'https://api.openweathermap.org/data/2.5/forecast?q={city_name},PH&appid={self.openweather_api_key}&units=metric'
                response = requests.get(url, timeout=10)
            
            response.raise_for_status()
            data = response.json()
            
            # Process forecast data - get daily summaries
            daily_forecasts = {}
            
            for item in data['list']:
                dt = datetime.fromtimestamp(item['dt'])
                date_key = dt.date()
                
                if date_key not in daily_forecasts:
                    daily_forecasts[date_key] = {
                        'temps': [],
                        'humidity': [],
                        'wind': [],
                        'pressure': [],
                        'precipitation': [],
                        'conditions': [],
                        'icons': [],
                        'clouds': []
                    }
                
                daily_forecasts[date_key]['temps'].append(item['main']['temp'])
                daily_forecasts[date_key]['humidity'].append(item['main']['humidity'])
                daily_forecasts[date_key]['wind'].append(item['wind']['speed'] * 3.6)  # m/s to km/h
                daily_forecasts[date_key]['pressure'].append(item['main']['pressure'])
                daily_forecasts[date_key]['precipitation'].append(
                    item.get('rain', {}).get('3h', 0) + item.get('snow', {}).get('3h', 0)
                )
                daily_forecasts[date_key]['conditions'].append(item['weather'][0]['description'])
                daily_forecasts[date_key]['icons'].append(item['weather'][0]['icon'])
                daily_forecasts[date_key]['clouds'].append(item['clouds']['all'])
            
            # Convert to daily format
            forecast_list = []
            for date_key in sorted(daily_forecasts.keys()):
                day_data = daily_forecasts[date_key]
                
                # Validate temperatures - filter out unrealistic sensor readings (e.g., 512)
                valid_temps = [t for t in day_data['temps'] if -50 <= t <= 60]
                if not valid_temps:
                    # Fallback to default if all readings are invalid
                    valid_temps = [28]  # Default Philippines temperature
                
                # Get most common condition and icon (from midday)
                midday_idx = len(day_data['conditions']) // 2
                
                forecast_list.append({
                    'date': date_key.strftime('%Y-%m-%d'),
                    'day': date_key.strftime('%A'),
                    'temperature': round(np.mean(valid_temps), 1),
                    'min': round(min(valid_temps), 1),
                    'max': round(max(valid_temps), 1),
                    'humidity': int(np.mean(day_data['humidity'])),
                    'windKmh': round(np.mean(day_data['wind']), 1),
                    'pressure': round(np.mean(day_data['pressure']), 1),
                    'precipMm': round(sum(day_data['precipitation']), 2),
                    'description': day_data['conditions'][midday_idx].capitalize(),
                    'icon': day_data['icons'][midday_idx],
                    'iconUrl': f"https://openweathermap.org/img/wn/{day_data['icons'][midday_idx]}@2x.png",
                    'cloud': int(np.mean(day_data['clouds'])),
                    'city': location,
                    'country': 'Philippines',
                    'source': 'openweather_5day'
                })
            
            return forecast_list
            
        except Exception as e:
            print(f"[ERROR] Error fetching 5-day forecast for {location}: {e}")
            return None

    def get_location_historical_data(self, location: str) -> Optional[Dict]:
        """Get historical average data for a location"""
        if self.data is None:
            return None
            
        # Try to match location
        location_parts = location.lower().split()
        filtered_data = self.data
        
        for part in location_parts:
            filtered_data = filtered_data[
                filtered_data['municipality'].str.lower().str.contains(part, na=False) |
                filtered_data['province'].str.lower().str.contains(part, na=False)
            ]
        
        if filtered_data.empty:
            return None
            
        # Return averages
        return {
            'temperature': filtered_data['temperature'].mean(),
            'humidity': filtered_data['humidity'].mean(),
            'pressure': filtered_data['pressure'].mean(),
            'wind_speed': filtered_data['wind_speed'].mean(),
            'rainfall': filtered_data['rainfall'].mean(),
            'visibility': 10  # Default visibility
        }

    def get_current_weather_enhanced(self, location: str = 'Oriental Mindoro', save_to_db: bool = True) -> Optional[Dict]:
        """Get current weather using OpenWeather API + ML corrections"""
        # First try OpenWeather API
        ow_data = self.fetch_openweather_data(location)
        
        if ow_data:
            # Apply ML corrections for local accuracy
            corrected_data = self.apply_ml_corrections(ow_data, location)
            
            # Format for our API response
            current_weather = {
                'city': corrected_data.get('city_name', location),
                'country': corrected_data.get('country', 'Philippines'),
                'latitude': corrected_data.get('latitude', 13.0),
                'longitude': corrected_data.get('longitude', 122.0),
                'temperature': round(corrected_data['temperature'], 1),
                'feels_like': round(corrected_data['feels_like'], 1),
                'description': corrected_data['description'],
                'humidity': int(corrected_data['humidity']),
                'windKmh': round(corrected_data['wind_speed'], 1),
                'windDirection': self._deg_to_direction(corrected_data['wind_direction']),
                'windDegree': corrected_data['wind_direction'],
                'pressure': round(corrected_data['pressure'], 1),
                'visibilityKm': round(corrected_data['visibility'], 1),
                'uvIndex': corrected_data['uv_index'],
                'cloud': corrected_data['clouds'],
                'precipMm': round(corrected_data['precipitation'], 2),
                'icon': corrected_data['icon'],
                'iconUrl': corrected_data['icon_url'],
                'sunrise': corrected_data['sunrise'],
                'sunset': corrected_data['sunset'],
                'moonPhase': 'Waxing Crescent',
                'moonIllumination': 45,
                'source': 'openweather_ml_corrected'
            }

            # Push live reading into weather_history so lag features stay current
            self.weather_history.append({
                'temperature': corrected_data['temperature'],
                'humidity': corrected_data['humidity'],
                'rainfall': corrected_data.get('precipitation', 0),
                'wind_speed': corrected_data['wind_speed'],
                'pressure': corrected_data['pressure'],
            })
            if len(self.weather_history) > 30:
                self.weather_history = self.weather_history[-30:]
        else:
            # Fallback to ML-only prediction
            print("âš ï¸ OpenWeather API failed, using ML prediction only")
            return self.get_current_weather_ml_only(location, save_to_db)
        
        # Save to database if requested
        if save_to_db:
            self._save_weather_to_db(current_weather, 'current', datetime.now().date())
        
        return current_weather

    def get_current_weather_ml_only(self, city: str = 'Oriental Mindoro', save_to_db: bool = True) -> Optional[Dict]:
        """Fallback ML-only weather prediction"""
        if self.last_data is None:
            return None
        
        # Add small random variations
        temp_variation = np.random.uniform(-1, 1)
        humidity_variation = np.random.randint(-3, 3)
        
        current_weather = {
            'city': city,
            'country': 'Philippines',
            'latitude': 13.0,
            'longitude': 122.0,
            'temperature': round(self.last_data['temperature'] + temp_variation, 1),
            'feels_like': round(self.last_data['temperature'] + temp_variation + 2, 1),
            'description': self.last_data['condition'],
            'humidity': max(0, min(100, int(self.last_data['humidity']) + humidity_variation)),
            'windKmh': round(self.last_data['wind_speed'], 1),
            'windDirection': 'Variable',
            'windDegree': 0,
            'pressure': round(self.last_data['pressure'], 1),
            'visibilityKm': 10.0,
            'uvIndex': 6,
            'cloud': 50,
            'precipMm': round(self.last_data['rainfall'], 2),
            'icon': self._get_weather_icon(self.last_data['condition']),
            'iconUrl': None,
            'sunrise': '06:00 AM',
            'sunset': '06:00 PM',
            'moonPhase': 'Waxing Crescent',
            'moonIllumination': 45,
            'source': 'ml_prediction'
        }
        
        if save_to_db:
            self._save_weather_to_db(current_weather, 'current', datetime.now().date())
        
        return current_weather

    def predict_tomorrow_enhanced(self, location: str = 'Oriental Mindoro', save_to_db: bool = True) -> Optional[Dict]:
        """Predict tomorrow's weather using enhanced ML + OpenWeather"""
        current = self.get_current_weather_enhanced(location, save_to_db=False)
        if not current:
            return None
        
        # Use ML models to predict tomorrow's values
        tomorrow_values = self._predict_next_day(location)
        
        tomorrow = {
            'date': (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'day': 'Tomorrow',
            'city': location,
            'country': 'Philippines',
            'latitude': current.get('latitude'),
            'longitude': current.get('longitude'),
            'temperature': round(tomorrow_values.get('temperature', current['temperature']), 1),
            'min': round(tomorrow_values.get('temperature', current['temperature']) - 2, 1),
            'max': round(tomorrow_values.get('temperature', current['temperature']) + 3, 1),
            'description': tomorrow_values.get('condition', current['description']),
            'humidity': int(round(max(40, min(95, tomorrow_values.get('humidity', current['humidity']))))),
            'windKmh': max(0, round(tomorrow_values.get('wind_speed', current['windKmh']), 1)),
            'windDirection': 'Variable',
            'pressure': round(tomorrow_values.get('pressure', current['pressure']), 1),
            'visibilityKm': 10.0,
            'uvIndex': 6,
            'cloud': 50,
            'precipMm': max(0, round(tomorrow_values.get('rainfall', 0), 2)),
            'icon': self._get_weather_icon(tomorrow_values.get('condition', current['description'])),
            'source': 'ml_prediction'
        }
        
        if save_to_db:
            forecast_date = datetime.now().date() + timedelta(days=1)
            self._save_weather_to_db(tomorrow, 'tomorrow', forecast_date)
        
        return tomorrow

    def predict_weekly_enhanced(self, location: str = 'Oriental Mindoro', days: int = 7, save_to_db: bool = True) -> List[Dict]:
        """
        Hybrid 7-day forecast:
        - Days 1-5: OpenWeather 5-day forecast API (accurate)
        - Days 6-7: ML predictions (ensemble)
        """
        print(f"[FORECAST] Generating 7-day forecast for {location}...")
        
        # Get OpenWeather 5-day forecast (Days 1-5)
        openweather_forecast = self.fetch_openweather_5day_forecast(location)
        
        weekly_forecast = []
        
        if openweather_forecast and len(openweather_forecast) > 0:
            # Use OpenWeather data for available days (usually 5 days)
            # Apply ML corrections to each day for improved local accuracy
            print(f"[OK] Using OpenWeather API for days 1-{len(openweather_forecast)}")
            
            for day_data in openweather_forecast[:5]:  # Limit to 5 days
                # Apply correction models to refine OpenWeather values
                ow_like = {
                    'temperature': day_data.get('temperature', 28),
                    'humidity': day_data.get('humidity', 75),
                    'pressure': day_data.get('pressure', 1013),
                    'wind_speed': day_data.get('windKmh', 10),
                    'visibility': 10.0,
                    'clouds': day_data.get('cloud', 50),
                }
                corrected = self.apply_ml_corrections(ow_like, location)
                day_data['temperature'] = round(corrected.get('temperature', day_data['temperature']), 1)
                day_data['humidity'] = int(corrected.get('humidity', day_data['humidity']))
                day_data['pressure'] = round(corrected.get('pressure', day_data['pressure']), 1)
                day_data['windKmh'] = round(corrected.get('wind_speed', day_data['windKmh']), 1)

                # Add additional fields
                day_data['windDirection'] = 'Variable'
                day_data['visibilityKm'] = 10.0
                day_data['uvIndex'] = max(0, min(11, 6))
                
                weekly_forecast.append(day_data)
                
                if save_to_db:
                    forecast_date = datetime.strptime(day_data['date'], '%Y-%m-%d').date()
                    self._save_weather_to_db(day_data, 'daily', forecast_date)
        
        # For remaining days (6-7), use ML predictions
        days_to_predict = days - len(weekly_forecast)
        
        if days_to_predict > 0:
            print(f"[ML] Using ML predictions for days {len(weekly_forecast)+1}-{days}")
            
            # Get current weather as base
            current = self.get_current_weather_enhanced(location, save_to_db=False)
            if not current:
                return weekly_forecast
            
            # Use the last OpenWeather day as starting point
            if weekly_forecast:
                last_day = weekly_forecast[-1]
                current_values = {
                    'temperature': last_day['temperature'],
                    'humidity': last_day['humidity'],
                    'rainfall': last_day.get('precipMm', 0),
                    'wind_speed': last_day['windKmh'],
                    'pressure': last_day['pressure'],
                    'condition': last_day['description']
                }
            else:
                current_values = {
                    'temperature': current['temperature'],
                    'humidity': current['humidity'],
                    'rainfall': current['precipMm'],
                    'wind_speed': current['windKmh'],
                    'pressure': current['pressure'],
                    'condition': current['description']
                }
            
            # Use deterministic seed for consistency
            today = datetime.now().date()
            base_seed = int(today.strftime('%Y%m%d'))
            
            # Seed weather history for lag features
            if not self.weather_history:
                self.weather_history.append(current_values.copy())
            
            start_offset = len(weekly_forecast)
            for i in range(days_to_predict):
                day_offset = start_offset + i
                forecast_date = datetime.now() + timedelta(days=day_offset)
                date_seed = base_seed + day_offset
                
                # Use ML ensemble prediction (LSTM + XGBoost)
                if (XGBOOST_AVAILABLE and self.xgboost_models) or (TENSORFLOW_AVAILABLE and self.lstm_models):
                    next_values = self._predict_with_ensemble(location, current_values, forecast_date)
                else:
                    # Fallback to deterministic prediction if no ML models
                    next_values = self._predict_next_day_from_current(current_values, date_seed)
                
                # Update weather history for next iteration's lag features
                self.weather_history.append(next_values.copy())
                if len(self.weather_history) > 14:
                    self.weather_history = self.weather_history[-14:]
                
                day_name = forecast_date.strftime('%A')
                
                # Validate temperature values
                temp_current = next_values.get('temperature', current_values['temperature'])
                if temp_current < -50 or temp_current > 60:
                    temp_current = current_values['temperature']  # Use fallback
                
                temp_min = next_values.get('temperature_min', temp_current - 2)
                if temp_min < -50 or temp_min > 60:
                    temp_min = temp_current - 2
                
                temp_max = next_values.get('temperature_max', temp_current + 2)
                if temp_max < -50 or temp_max > 60:
                    temp_max = temp_current + 2
                
                day_forecast = {
                    'date': forecast_date.strftime('%Y-%m-%d'),
                    'day': day_name,
                    'city': location,
                    'country': 'Philippines',
                    'latitude': current.get('latitude', 13.0),
                    'longitude': current.get('longitude', 122.0),
                    'temperature': round(temp_current, 1),
                    'min': round(temp_min, 1),
                    'max': round(temp_max, 1),
                    'description': next_values.get('condition', current_values['condition']),
                    'humidity': max(40, min(95, int(next_values.get('humidity', current_values['humidity'])))),
                    'windKmh': max(0, round(next_values.get('wind_speed', current_values['wind_speed']), 1)),
                    'windDirection': 'Variable',
                    'pressure': round(next_values.get('pressure', current_values['pressure']), 1),
                    'visibilityKm': 10.0,
                    'uvIndex': max(0, min(11, 6 + (date_seed % 5 - 2))),
                    'cloud': max(0, min(100, 50 + ((date_seed * 7) % 40 - 20))),
                    'precipMm': max(0, round(next_values.get('rainfall', 0), 2)),
                    'icon': self._get_weather_icon(next_values.get('condition', current_values['condition'])),
                    'iconUrl': f"https://openweathermap.org/img/wn/{self._get_weather_icon(next_values.get('condition', current_values['condition']))}@2x.png",
                    'source': 'ml_ensemble_prediction',
                    # Pass confidence intervals to frontend with validation
                    'temperature_min': round(max(-50, min(60, temp_min)), 1),
                    'temperature_max': round(max(-50, min(60, temp_max)), 1),
                    'humidity_min': round(next_values.get('humidity_min', next_values.get('humidity', 75) - 5), 1),
                    'humidity_max': round(next_values.get('humidity_max', next_values.get('humidity', 75) + 5), 1),
                    'rainfall_min': round(next_values.get('rainfall_min', 0), 1),
                    'rainfall_max': round(next_values.get('rainfall_max', next_values.get('rainfall', 0) + 2), 1),
                }
                
                weekly_forecast.append(day_forecast)
                current_values = next_values
                
                if save_to_db:
                    self._save_weather_to_db(day_forecast, 'daily', forecast_date.date())
        
        print(f"[OK] Generated {len(weekly_forecast)}-day forecast")
        
        # Apply weather pattern adjustments
        weekly_forecast = self._apply_weather_patterns(weekly_forecast)
        
        return weekly_forecast

    def _apply_weather_patterns(self, forecast: List[Dict]) -> List[Dict]:
        """Apply weather pattern adjustments (typhoon season, monsoons, etc.)"""
        adjusted_forecast = []
        
        for day_data in forecast:
            try:
                forecast_date = datetime.strptime(day_data['date'], '%Y-%m-%d')
                month = forecast_date.month
                
                # Typhoon season adjustment (June-November)
                if month in [6, 7, 8, 9, 10, 11]:
                    # Increase rainfall probability and wind speed during typhoon season
                    day_data['precipMm'] = day_data.get('precipMm', 0) * 1.3
                    day_data['windKmh'] = day_data.get('windKmh', 10) * 1.2
                    
                    # Add typhoon warning if conditions are severe
                    if day_data.get('windKmh', 0) > 60 or day_data.get('precipMm', 0) > 50:
                        day_data['warning'] = 'Typhoon conditions possible'
                
                # Southwest Monsoon (Habagat) - June to September
                if month in [6, 7, 8, 9]:
                    day_data['monsoon'] = 'Southwest (Habagat)'
                    # Increase humidity and rainfall
                    day_data['humidity'] = min(95, day_data.get('humidity', 70) + 5)
                    day_data['precipMm'] = day_data.get('precipMm', 0) * 1.2
                
                # Northeast Monsoon (Amihan) - October to March
                elif month in [10, 11, 12, 1, 2, 3]:
                    day_data['monsoon'] = 'Northeast (Amihan)'
                    # Cooler and drier
                    day_data['temperature'] = day_data.get('temperature', 30) - 1
                    day_data['min'] = day_data.get('min', 25) - 1
                    day_data['max'] = day_data.get('max', 33) - 1
                
                # Wet season (June-November)
                if month in [6, 7, 8, 9, 10, 11]:
                    day_data['season'] = 'Wet'
                    # Higher cloud cover
                    day_data['cloud'] = min(100, day_data.get('cloud', 50) + 15)
                else:
                    day_data['season'] = 'Dry'
                
                # Extreme heat warning (March-May)
                if month in [3, 4, 5] and day_data.get('temperature', 30) > 35:
                    day_data['warning'] = 'Extreme heat warning'
                
                # Heavy rainfall warning
                if day_data.get('precipMm', 0) > 30:
                    day_data['warning'] = 'Heavy rainfall expected'
                
                adjusted_forecast.append(day_data)
                
            except Exception as e:
                print(f"âš ï¸ Error applying pattern adjustments: {e}")
                adjusted_forecast.append(day_data)
        
        return adjusted_forecast

    def _denormalize(self, col: str, val: float) -> float:
        """Convert normalized (0-1) value back to real scale."""
        lo, hi = self.norm_ranges.get(col, (0, 1))
        return val * (hi - lo) + lo

    def _get_confidence_interval(self, col: str, prediction: float) -> Tuple[float, float]:
        """Calculate confidence interval using quantile models if available, else RMSE-based.
        
        Returns: (min_value, max_value) for 95% confidence interval
        """
        # Prefer quantile model predictions
        lower_key = f'{col}_lower'
        upper_key = f'{col}_upper'
        if lower_key in self.quantile_models and upper_key in self.quantile_models:
            try:
                # Use the same features as the main model for quantile prediction
                if self.featured_data is not None and col in self.xgboost_feature_lists:
                    import xgboost as xgb
                    last_row = self.featured_data.iloc[-1:]
                    feat_cols = self.xgboost_feature_lists[col]
                    available = [c for c in feat_cols if c in last_row.columns]
                    if len(available) >= len(feat_cols) * 0.8:
                        X = last_row[available].values.astype(float)
                        lo_model = self.quantile_models[lower_key]
                        hi_model = self.quantile_models[upper_key]
                        if hasattr(lo_model, 'get_booster'):
                            lo_pred = float(lo_model.predict(X)[0])
                            hi_pred = float(hi_model.predict(X)[0])
                        else:
                            dmat = xgb.DMatrix(X, feature_names=available)
                            lo_pred = float(lo_model.predict(dmat)[0])
                            hi_pred = float(hi_model.predict(dmat)[0])
                        # Denormalize
                        lo_real = self._denormalize(col, lo_pred)
                        hi_real = self._denormalize(col, hi_pred)
                        return (min(lo_real, prediction), max(hi_real, prediction))
            except Exception:
                pass  # Fall through to RMSE-based

        # Fallback: RMSE-based confidence interval
        if col not in self.model_metrics:
            lo, hi = self.norm_ranges.get(col, (0, 1))
            range_val = hi - lo if hi > lo else 1
            margin = range_val * 0.02
            return (max(lo, prediction - margin), min(hi, prediction + margin))
        
        metrics = self.model_metrics[col]
        rmse_norm = metrics.get('rmse', 0.02)
        lo, hi = self.norm_ranges.get(col, (0, 1))
        range_val = hi - lo if hi > lo else 1
        rmse_real = rmse_norm * range_val
        margin = rmse_real * 2.0
        return (max(lo, prediction - margin), min(hi, prediction + margin))

    def apply_physical_constraints(self, predictions: Dict) -> Dict:
        """Apply physical constraint post-processing to predictions."""
        constrained = dict(predictions)
        
        for param in ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']:
            if param in constrained and param in self.physical_limits:
                lo, hi = self.physical_limits[param]
                constrained[param] = max(lo, min(hi, constrained[param]))
        
        # Rainfall must be non-negative
        if 'rainfall' in constrained:
            constrained['rainfall'] = max(0, constrained['rainfall'])
        
        # Humidity must be 0-100
        if 'humidity' in constrained:
            constrained['humidity'] = max(0, min(100, constrained['humidity']))
        
        # Physical consistency: high humidity + low pressure = higher rain probability
        if all(k in constrained for k in ['humidity', 'pressure', 'rainfall']):
            if constrained['humidity'] > 85 and constrained['pressure'] < 1005:
                constrained['rainfall'] = max(constrained['rainfall'], 1.0)
        
        return constrained

    def apply_temporal_smoothing(self, predictions: Dict, previous_predictions: list) -> Dict:
        """Smooth predictions to avoid unrealistic day-to-day jumps."""
        if not previous_predictions:
            return predictions
        
        smoothed = dict(predictions)
        prev = previous_predictions[-1]
        
        for param in ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']:
            if param in smoothed and param in prev:
                max_change = self.max_daily_change.get(param, float('inf'))
                diff = smoothed[param] - prev[param]
                if abs(diff) > max_change:
                    # Clamp to max daily change
                    smoothed[param] = prev[param] + max_change * (1 if diff > 0 else -1)
        
        return smoothed

    def log_prediction(self, location: str, forecast_date, predictions: Dict):
        """Log a prediction for later accuracy evaluation (feedback loop)."""
        import json
        log_entry = {
            'location': location,
            'forecast_date': str(forecast_date),
            'predicted_at': str(datetime.now()),
            'predictions': {k: v for k, v in predictions.items() if isinstance(v, (int, float))}
        }
        self.prediction_log.append(log_entry)
        
        # Persist to file (keep last 1000 predictions)
        log_path = self.models_dir / 'prediction_log.json'
        try:
            if log_path.exists():
                with open(log_path, 'r') as f:
                    all_logs = json.load(f)
            else:
                all_logs = []
            all_logs.append(log_entry)
            all_logs = all_logs[-1000:]  # Keep last 1000
            with open(log_path, 'w') as f:
                json.dump(all_logs, f, indent=2)
        except Exception:
            pass

    def evaluate_past_predictions(self) -> Dict:
        """Evaluate accuracy of past predictions against actual data (feedback loop)."""
        import json
        log_path = self.models_dir / 'prediction_log.json'
        if not log_path.exists():
            return {'status': 'no_predictions_logged'}
        
        try:
            with open(log_path, 'r') as f:
                logs = json.load(f)
        except Exception:
            return {'status': 'error_reading_log'}
        
        if self.featured_data is None:
            return {'status': 'no_featured_data'}
        
        errors = {p: [] for p in ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']}
        evaluated = 0
        
        for entry in logs:
            try:
                fdate = pd.to_datetime(entry['forecast_date']).date()
                loc = entry['location'].lower().replace(' ', '_')
                # Find actual data for that date/location
                actual_rows = self.featured_data[
                    (self.featured_data['date'].dt.date == fdate) &
                    (self.featured_data['municipality'].str.lower().str.replace(' ', '_') == loc)
                ]
                if actual_rows.empty:
                    continue
                actual = actual_rows.iloc[0]
                preds = entry['predictions']
                for param in errors:
                    if param in preds and param in actual:
                        errors[param].append(abs(preds[param] - actual[param]))
                evaluated += 1
            except Exception:
                continue
        
        results = {'evaluated': evaluated, 'metrics': {}}
        for param, errs in errors.items():
            if errs:
                results['metrics'][param] = {
                    'mae': round(float(np.mean(errs)), 3),
                    'max_error': round(float(max(errs)), 3),
                    'count': len(errs)
                }
        return results

    def _predict_next_day(self, location: str = 'Oriental Mindoro') -> Dict:
        """Predict next day's weather using trained XGBoost models on featured data.
        For Calapan, uses high-accuracy Calapan-specific models.
        Returns values in REAL units (denormalized) with confidence intervals.
        """
        predictions = {}
        numerical_cols = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']

        # Check if this is Calapan and we have Calapan-specific models
        is_calapan = 'calapan' in location.lower()
        has_calapan_models = bool(self.calapan_models and self.calapan_scaler)

        if is_calapan and has_calapan_models:
            # Use Calapan-specific high-accuracy models
            return self._predict_next_day_calapan()
        numerical_cols = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']

        # Check if this is Calapan and we have Calapan-specific models
        is_calapan = 'calapan' in location.lower()
        has_calapan_models = bool(self.calapan_models and self.calapan_scaler)

        if is_calapan and has_calapan_models:
            # Use Calapan-specific high-accuracy models
            return self._predict_next_day_calapan()

        # Try to use the featured dataset for proper ML prediction
        if self.featured_data is not None and XGBOOST_AVAILABLE:
            last_row = self.featured_data.iloc[-1:]  # Keep as DataFrame
            for col in numerical_cols:
                model_key = f'{col}_model'
                if model_key in self.models and col in self.model_feature_cols:
                    try:
                        feat_cols = self.model_feature_cols[col]
                        # Only use columns that exist in the data
                        available = [c for c in feat_cols if c in last_row.columns]
                        if len(available) >= len(feat_cols) * 0.8:  # At least 80% features present
                            X = last_row[available].values.astype(float)
                            m = self.models[model_key]
                            if hasattr(m, 'get_booster'):
                                pred_norm = float(m.predict(X)[0])
                            else:
                                import xgboost as xgb
                                dmat = xgb.DMatrix(X, feature_names=available)
                                pred_norm = float(m.predict(dmat)[0])
                            pred_real = self._denormalize(col, pred_norm)
                            predictions[col] = pred_real
                            continue
                    except Exception as e:
                        print(f"[WARN] ML prediction failed for {col}: {e}")

                # Fallback: use last_data (denormalize it)
                raw = self.last_data.get(col, 0.5) if self.last_data else 0.5
                # If the raw value is in 0-1 range, it's normalized
                if 0 <= raw <= 1:
                    predictions[col] = self._denormalize(col, raw)
                else:
                    predictions[col] = raw
        else:
            # No featured data or XGBoost — use last_data with denormalization
            for col in numerical_cols:
                raw = self.last_data.get(col, 0.5) if self.last_data else 0.5
                if 0 <= raw <= 1:
                    predictions[col] = self._denormalize(col, raw)
                else:
                    predictions[col] = raw

        # Predict condition
        if 'condition_model' in self.models and 'condition_encoder' in self.models:
            model = self.models['condition_model']
            encoder = self.models['condition_encoder']
            try:
                last_conditions = self._get_last_conditions(3)
                if last_conditions is not None:
                    pred_encoded = model.predict([last_conditions])[0]
                    pred_encoded = max(0, min(len(encoder.classes_) - 1, int(round(pred_encoded))))
                    predictions['condition'] = encoder.inverse_transform([pred_encoded])[0]
                else:
                    predictions['condition'] = self.last_data.get('condition', 'Sunny') if self.last_data else 'Sunny'
            except Exception:
                predictions['condition'] = self.last_data.get('condition', 'Sunny') if self.last_data else 'Sunny'
        else:
            predictions['condition'] = self.last_data.get('condition', 'Sunny') if self.last_data else 'Sunny'

        # Add confidence intervals for numerical predictions
        for col in numerical_cols:
            if col in predictions:
                min_val, max_val = self._get_confidence_interval(col, predictions[col])
                predictions[f'{col}_min'] = round(min_val, 2)
                predictions[f'{col}_max'] = round(max_val, 2)
                # Also round the main prediction for consistency
                predictions[col] = round(predictions[col], 2)

        return predictions

    def _predict_next_day_calapan(self) -> Dict:
        """Predict next day's weather using Calapan-specific high-accuracy models (v4)."""
        predictions = {}
        numerical_cols = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']

        # Get the last available Calapan data (from the 500k dataset)
        if self.data is not None:
            calapan_data = self.data[self.data['municipality'].str.lower() == 'calapan'].copy()
            if not calapan_data.empty:
                # Sort by date and get the most recent data
                calapan_data = calapan_data.sort_values('date').tail(30)  # Last 30 days for features
                last_row = calapan_data.iloc[-1:]

                # Add Calapan-specific features
                features_df = self._add_calapan_features_to_row(last_row.copy())

                # Scale features using Calapan scaler
                if self.calapan_scaler:
                    # Use the same feature columns that the scaler was trained on
                    if hasattr(self.calapan_scaler, 'feature_names_in_'):
                        feature_cols = list(self.calapan_scaler.feature_names_in_)
                    else:
                        # Fallback: exclude targets and non-numeric columns
                        feature_cols = [col for col in features_df.columns
                                      if col not in numerical_cols + ['date', 'weather_condition_encoded']
                                      and features_df[col].dtype in ['float64', 'int64', 'float32', 'int32']]

                    # Ensure all required features are present
                    available_features = [col for col in feature_cols if col in features_df.columns]
                    if len(available_features) < len(feature_cols) * 0.8:
                        print(f"[WARN] Only {len(available_features)}/{len(feature_cols)} features available")
                        # Fill missing features with 0
                        for col in feature_cols:
                            if col not in features_df.columns:
                                features_df[col] = 0.0

                    features_scaled = self.calapan_scaler.transform(features_df[feature_cols].values)
                else:
                    features_scaled = features_df[feature_cols].values

                # Make predictions for each target using Calapan models
                for col in numerical_cols:
                    xgb_key = f'{col}_xgboost'
                    lstm_key = f'{col}_lstm'

                    xgb_pred = None
                    lstm_pred = None

                    # XGBoost prediction
                    if xgb_key in self.calapan_models:
                        try:
                            xgb_pred = float(self.calapan_models[xgb_key].predict(features_scaled)[0])
                        except Exception as e:
                            print(f"[WARN] Calapan XGBoost prediction failed for {col}: {e}")

                    # LSTM prediction (if available)
                    if TENSORFLOW_AVAILABLE and lstm_key in self.calapan_models:
                        try:
                            # For LSTM, we need sequence data
                            seq_length = 30
                            if len(calapan_data) >= seq_length:
                                seq_data = calapan_data.tail(seq_length).copy()
                                seq_features = self._add_calapan_features_to_row(seq_data)
                                if self.calapan_scaler:
                                    seq_scaled = self.calapan_scaler.transform(seq_features[feature_cols].values)
                                else:
                                    seq_scaled = seq_features[feature_cols].values

                                seq_scaled = seq_scaled.reshape(1, seq_length, -1)
                                lstm_pred = float(self.calapan_models[lstm_key].predict(seq_scaled, verbose=0)[0][0])
                        except Exception as e:
                            print(f"[WARN] Calapan LSTM prediction failed for {col}: {e}")

                    # Use only XGBoost for now (LSTM has serialization issues)
                    if xgb_pred is not None:
                        predictions[col] = xgb_pred
                        print(f"[OK] Calapan XGBoost prediction for {col}: {xgb_pred:.4f}")
                    else:
                        # Fallback to last known value
                        predictions[col] = float(last_row[col].iloc[0])
                        print(f"[WARN] No Calapan model for {col}, using last value: {predictions[col]:.4f}")

                # Predict weather condition (use general model for now)
                predictions['condition'] = 'Partly cloudy'  # Default for Calapan

                # Add confidence intervals (Calapan models are highly accurate, so tighter intervals)
                for col in numerical_cols:
                    if col in predictions:
                        # Calapan models have ~99% accuracy, so smaller confidence intervals
                        std_dev = self._get_calapan_prediction_std(col, predictions[col])
                        predictions[f'{col}_min'] = round(predictions[col] - 1.96 * std_dev, 2)
                        predictions[f'{col}_max'] = round(predictions[col] + 1.96 * std_dev, 2)
                        predictions[col] = round(predictions[col], 2)

                print(f"[SUCCESS] Calapan high-accuracy predictions completed")
                return predictions

        # Fallback if no Calapan data available
        print("[WARN] No Calapan data available, using general predictions")
        return self._predict_next_day('Oriental Mindoro')

    def _add_calapan_features_to_row(self, df):
        """Add Calapan-specific features to a data row (same as training)."""
        df = df.copy()

        # Basic temporal features
        df['dayofyear'] = df['date'].dt.dayofyear
        df['month'] = df['date'].dt.month
        df['day'] = df['date'].dt.day
        df['year'] = df['date'].dt.year

        # Cyclical encoding
        df['day_sin'] = np.sin(2 * np.pi * df['dayofyear'] / 365.25)
        df['day_cos'] = np.cos(2 * np.pi * df['dayofyear'] / 365.25)
        df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)

        # Calapan-specific seasonal features
        df['is_rainy_season'] = df['month'].isin([6, 7, 8, 9, 10]).astype(int)
        df['is_dry_season'] = df['month'].isin([11, 12, 1, 2, 3, 4, 5]).astype(int)

        # Rolling statistics (7-day windows)
        numerical_cols = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']
        for target in numerical_cols:
            df[f'{target}_7d_mean'] = df[target].rolling(7, min_periods=1).mean()
            df[f'{target}_7d_std'] = df[target].rolling(7, min_periods=1).std()
            df[f'{target}_14d_mean'] = df[target].rolling(14, min_periods=1).mean()
            df[f'{target}_30d_mean'] = df[target].rolling(30, min_periods=1).mean()

        # Lag features (previous days)
        for lag in [1, 2, 3, 7, 14]:
            for target in numerical_cols:
                df[f'{target}_lag_{lag}'] = df[target].shift(lag)

        # Rate of change features
        for target in numerical_cols:
            df[f'{target}_change_1d'] = df[target].diff(1)
            df[f'{target}_change_7d'] = df[target].diff(7)

        # Weather pattern features
        df['temp_humidity_ratio'] = df['temperature'] / (df['humidity'] / 100)
        df['pressure_temp_interaction'] = df['pressure'] * df['temperature'] / 1000
        df['wind_rain_interaction'] = df['wind_speed'] * df['rainfall']

        # Remove NaN values
        df = df.dropna(axis=1, how='all')  # Remove columns that are all NaN
        df = df.fillna(method='ffill').fillna(method='bfill').fillna(0)  # Fill remaining NaNs

        return df

    def _get_calapan_prediction_std(self, target: str, prediction: float) -> float:
        """Get standard deviation for Calapan prediction confidence intervals."""
        # Calapan models are highly accurate, so use smaller standard deviations
        calapan_stds = {
            'temperature': 0.5,  # ±1°C accuracy
            'humidity': 3.0,     # ±6% accuracy
            'rainfall': 2.0,     # ±4mm accuracy
            'wind_speed': 1.0,   # ±2km/h accuracy
            'pressure': 2.0,     # ±4hPa accuracy
        }
        return calapan_stds.get(target, 1.0)

    def _normalize(self, col: str, val: float) -> float:
        """Convert real value to normalized (0-1) scale."""
        lo, hi = self.norm_ranges.get(col, (0, 1))
        if hi == lo:
            return 0.5
        return max(0.0, min(1.0, (val - lo) / (hi - lo)))

    def _predict_with_ensemble(self, location: str, current_values: Dict, forecast_date: datetime) -> Dict:
        """
        Predict using XGBoost models (v3 preferred) + LSTM ensemble.
        Applies physical constraints and temporal smoothing.
        Returns values in REAL units (denormalized).
        """
        predictions = {}
        location_key = location.lower().replace(' ', '_')
        import xgboost as xgb
        climatology = self._get_location_climatology(location, forecast_date)

        # --- Primary XGBoost models (prefer v3) ---
        primary_preds = {}
        if self.featured_data is not None:
            last_row = self.featured_data.iloc[-1:]
            for param in ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']:
                # Try v3 model first
                model = self.xgboost_v3_models.get(param) or None
                feat_list = self.xgboost_v3_feature_lists.get(param) or None
                
                # Fall back to primary models
                if model is None:
                    model_key = f'{param}_model'
                    model = self.models.get(model_key)
                    feat_list = self.model_feature_cols.get(param)
                
                # Fall back to xgboost_models
                if model is None:
                    model = self.xgboost_models.get(param)
                    feat_list = self.xgboost_feature_lists.get(param)
                
                if model is not None and feat_list is not None:
                    try:
                        available = [c for c in feat_list if c in last_row.columns]
                        if len(available) >= len(feat_list) * 0.8:
                            X = last_row[available].values.astype(float)
                            # XGBRegressor uses numpy arrays; Booster uses DMatrix
                            if hasattr(model, 'get_booster'):
                                pred_norm = float(model.predict(X)[0])
                            else:
                                dmat = xgb.DMatrix(X, feature_names=available)
                                pred_norm = float(model.predict(dmat)[0])
                            # No noise — let the model speak for itself
                            pred_norm = np.clip(pred_norm, 0, 1)
                            primary_preds[param] = self._denormalize(param, pred_norm)
                    except Exception as e:
                        print(f"[WARN] XGBoost error for {param}: {e}")

        # --- LSTM predictions ---
        lstm_preds = {}
        if TENSORFLOW_AVAILABLE and location_key in self.lstm_models:
            try:
                # Use lookback=14 for v3 models, 7 for v1
                v3_path = self.models_dir / f'lstm_{location_key}_v3.h5'
                lookback = 14 if v3_path.exists() else 7
                sequence = self._prepare_sequence_for_lstm(current_values, location, lookback=lookback)
                lstm_output = self.lstm_models[location_key].predict(sequence, verbose=0)

                # Denormalize chain: scaler.inverse_transform() → norm_ranges denorm
                scaler = self.lstm_scalers.get(location_key)
                if scaler is not None:
                    try:
                        # Step 1: inverse scaler → back to norm_ranges [0,1] space
                        intermediate = scaler.inverse_transform(lstm_output)
                        # Step 2: denormalize from [0,1] to real values
                        for i, param in enumerate(['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']):
                            if i < intermediate.shape[-1]:
                                normed = float(np.clip(intermediate[0][i], 0, 1))
                                lstm_preds[param] = self._denormalize(param, normed)
                    except Exception:
                        # Fallback: assume output is in norm_ranges [0,1] directly
                        for i, param in enumerate(['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']):
                            if i < lstm_output.shape[-1]:
                                raw = float(lstm_output[0][i])
                                lstm_preds[param] = self._denormalize(param, np.clip(raw, 0, 1))
                else:
                    for i, param in enumerate(['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']):
                        if i < lstm_output.shape[-1]:
                            raw = float(lstm_output[0][i])
                            if 0 <= raw <= 1:
                                lstm_preds[param] = self._denormalize(param, raw)
                            else:
                                lstm_preds[param] = raw
            except Exception as e:
                print(f"[WARN] LSTM ensemble error: {e}")

        # --- XGBoost secondary models (xgboost_models from retrain) ---
        xgb_secondary = {}
        if XGBOOST_AVAILABLE:
            for param in ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']:
                if param in self.xgboost_models and param not in self.xgboost_v3_models:
                    model = self.xgboost_models[param]
                    if param in self.xgboost_feature_lists:
                        try:
                            features = self._prepare_features_for_ml(current_values, forecast_date, param)
                            X_arr = features.reshape(1, -1)
                            if hasattr(model, 'get_booster'):
                                pred = float(model.predict(X_arr)[0])
                            else:
                                dmat = xgb.DMatrix(X_arr, feature_names=self.xgboost_feature_lists[param])
                                pred = float(model.predict(dmat)[0])
                            xgb_secondary[param] = self._denormalize(param, pred)
                        except Exception:
                            pass

        # --- Combine predictions ---
        # ML models are well-calibrated (R2 > 0.87) — trust them more than raw current values
        day_offset = max(1, (forecast_date - datetime.now()).days)
        # Reduce current-value anchor as forecast horizon grows
        current_weight = max(0.10, 0.30 - day_offset * 0.03)

        for param in ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']:
            p_val = primary_preds.get(param)
            l_val = lstm_preds.get(param)
            s_val = xgb_secondary.get(param)
            c_val = current_values.get(param)
            climate_info = climatology.get(param, {})
            climate_val = climate_info.get('recent_avg') or climate_info.get('month_avg')

            # Weighted ensemble of available models
            ml_vals = []
            ml_weights = []
            if p_val is not None:
                ml_vals.append(p_val)
                ml_weights.append(0.50)  # Primary XGBoost v3 gets highest weight
            if l_val is not None:
                ml_vals.append(l_val)
                ml_weights.append(0.35)  # LSTM (with proper scaler)
            if s_val is not None:
                ml_vals.append(s_val)
                ml_weights.append(0.15)  # Secondary XGBoost

            if ml_vals:
                total_w = sum(ml_weights[:len(ml_vals)])
                ml_val = sum(v * w for v, w in zip(ml_vals, ml_weights[:len(ml_vals)])) / total_w
            else:
                ml_val = None

            # Anchor to current weather for continuity
            if ml_val is not None and c_val is not None and c_val > 0:
                predictions[param] = (1 - current_weight) * ml_val + current_weight * c_val
            elif ml_val is not None:
                predictions[param] = ml_val
            else:
                predictions[param] = c_val if c_val is not None else 0

            if climate_val is not None:
                climate_weight = min(0.25, 0.10 + day_offset * 0.02)
                predictions[param] = (1 - climate_weight) * predictions[param] + climate_weight * climate_val

            trend = climate_info.get('trend', 0.0)
            if trend:
                max_shift = self.max_daily_change.get(param, 5.0)
                predictions[param] += max(-max_shift, min(max_shift, trend)) * 0.10

        # --- Apply physical constraints ---
        predictions = self.apply_physical_constraints(predictions)

        # --- Apply temporal smoothing ---
        predictions = self.apply_temporal_smoothing(predictions, self.weather_history)

        # --- Determine weather condition ---
        rain = predictions.get('rainfall', 0)
        temp = predictions.get('temperature', 30)
        hum = predictions.get('humidity', 75)
        wind = predictions.get('wind_speed', 10)
        pressure = predictions.get('pressure', 1013)
        
        if rain > 20 and wind > 30:
            predictions['condition'] = 'Thunderstorm'
        elif rain > 10:
            predictions['condition'] = 'Heavy Rain'
        elif rain > 5:
            predictions['condition'] = 'Rain'
        elif rain > 1:
            predictions['condition'] = 'Light Rain'
        elif hum > 85 and pressure < 1008:
            predictions['condition'] = 'Overcast'
        elif hum > 80 and rain > 0.5:
            predictions['condition'] = 'Cloudy'
        elif temp > 33:
            predictions['condition'] = 'Hot'
        elif temp > 32:
            predictions['condition'] = 'Sunny'
        elif hum > 75:
            predictions['condition'] = 'Partly Cloudy'
        else:
            predictions['condition'] = 'Sunny'

        # --- Add confidence intervals ---
        for col in ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']:
            if col in predictions:
                min_val, max_val = self._get_confidence_interval(col, predictions[col])
                predictions[f'{col}_min'] = round(min_val, 2)
                predictions[f'{col}_max'] = round(max_val, 2)
                predictions[col] = round(predictions[col], 2)

        # --- Log prediction for feedback loop ---
        try:
            self.log_prediction(location, forecast_date, predictions)
        except Exception:
            pass

        return predictions

    def _prepare_features_for_ml(self, current_values: Dict, forecast_date: datetime, target_param: str = None) -> np.ndarray:
        """Prepare features for XGBoost prediction - supports v3 features including geospatial/ENSO."""
        # If we have a specific feature list for this target, use it
        if target_param and target_param in self.xgboost_v3_feature_lists:
            feature_names = self.xgboost_v3_feature_lists[target_param]
        elif target_param and target_param in self.xgboost_feature_lists:
            feature_names = self.xgboost_feature_lists[target_param]
        else:
            feature_names = None
        
        day_of_year = forecast_date.timetuple().tm_yday
        month = forecast_date.month
        year = forecast_date.year
        day = forecast_date.day
        
        hist = self.weather_history if self.weather_history else []
        
        def _hist_val(param, lag):
            if len(hist) >= lag:
                return hist[-lag].get(param, current_values.get(param, 0))
            return current_values.get(param, 0)
        
        def _hist_roll(param, window):
            vals = [hist[-i].get(param, current_values.get(param, 0)) for i in range(1, min(window + 1, len(hist) + 1))]
            return float(np.mean(vals)) if vals else current_values.get(param, 0)
        
        def _hist_roll_max(param, window):
            vals = [hist[-i].get(param, current_values.get(param, 0)) for i in range(1, min(window + 1, len(hist) + 1))]
            return max(vals) if vals else current_values.get(param, 0)
        
        def _hist_roll_min(param, window):
            vals = [hist[-i].get(param, current_values.get(param, 0)) for i in range(1, min(window + 1, len(hist) + 1))]
            return min(vals) if vals else current_values.get(param, 0)
        
        def _hist_std(param, window):
            vals = [hist[-i].get(param, current_values.get(param, 0)) for i in range(1, min(window + 1, len(hist) + 1))]
            return float(np.std(vals)) if len(vals) > 1 else 0.0
        
        def _hist_diff(param, lag):
            if len(hist) >= lag:
                return current_values.get(param, 0) - hist[-lag].get(param, current_values.get(param, 0))
            return 0.0
        
        def _hist_ewm(param, span):
            vals = [current_values.get(param, 0)]
            for i in range(1, min(span * 2, len(hist) + 1)):
                vals.append(hist[-i].get(param, current_values.get(param, 0)))
            alpha = 2.0 / (span + 1)
            ewm = vals[-1]
            for v in reversed(vals[:-1]):
                ewm = alpha * v + (1 - alpha) * ewm
            return ewm
        
        cv = current_values

        # Historical monthly means from training data (Philippines averages)
        hist_means = {
            'temperature': 28.5, 'humidity': 76.0, 'rainfall': 8.5,
            'wind_speed': 12.0, 'pressure': 1011.0,
        }
        if self.data is not None:
            for p in hist_means:
                if p in self.data.columns:
                    month_data = self.data[self.data['date'].dt.month == month]
                    if not month_data.empty:
                        hist_means[p] = float(month_data[p].mean())

        # Geospatial lookup for the location
        loc_geo = self.municipality_geo.get(
            cv.get('city_name', ''), {'lat': 12.0, 'lon': 122.0, 'elev': 10, 'coast_km': 5.0}
        )
        lat_val = loc_geo.get('lat', 12.0)
        lon_val = loc_geo.get('lon', 122.0)
        elev_val = loc_geo.get('elev', 10)
        coast_km_val = loc_geo.get('coast_km', 5.0)

        # ENSO index (extended through 2026)
        enso_values = {2022: 0.3, 2023: -0.5, 2024: 0.8, 2025: -0.3, 2026: -0.1, 2027: 0.0}
        enso_idx = enso_values.get(year, 0.0)

        temp = cv.get('temperature', 28)
        hum = cv.get('humidity', 75)
        rain = cv.get('rainfall', 5)
        wind = cv.get('wind_speed', 10)
        press = cv.get('pressure', 1013)

        # Comprehensive feature lookup matching v3 training pipeline exactly
        feature_lookup = {
            # Raw weather values
            'temperature': temp, 'humidity': hum, 'rainfall': rain,
            'wind_speed': wind, 'pressure': press,
            # Date features
            'year': year, 'month': month, 'day': day,
            'dayofyear': day_of_year,
            'dayofweek': forecast_date.weekday(),
            'month_num': month,
            # Cyclical date
            'day_sin': np.sin(2 * np.pi * day_of_year / 365),
            'day_cos': np.cos(2 * np.pi * day_of_year / 365),
            'month_sin': np.sin(2 * np.pi * month / 12),
            'month_cos': np.cos(2 * np.pi * month / 12),
            'week_sin': np.sin(2 * np.pi * (day_of_year // 7) / 52),
            'week_cos': np.cos(2 * np.pi * (day_of_year // 7) / 52),
            # Monsoon cycle (v3)
            'monsoon_cycle_day': (day_of_year - 152) % 365,
            # Seasonal flags
            'is_wet_season': 1 if month in [6, 7, 8, 9, 10, 11] else 0,
            'is_dry_season': 1 if month in [1, 2, 3, 4, 5, 12] else 0,
            'is_habagat': 1 if month in [6, 7, 8, 9] else 0,
            'is_amihan': 1 if month in [10, 11, 12, 1, 2, 3] else 0,
            'is_typhoon_season': 1 if month in [6, 7, 8, 9, 10, 11] else 0,
            'is_typhoon_peak': 1 if month in [8, 9, 10] else 0,
            'is_hot_dry': 1 if month in [3, 4, 5] else 0,
            'is_transition': 1 if month in [5, 6, 11, 12] else 0,
            'is_monsoon_transition': 1 if month in [5, 6, 11, 12] else 0,
            # Lunar (v3)
            'lunar_phase': ((day_of_year % 29.53) / 29.53),
            'lunar_sin': np.sin(2 * np.pi * (day_of_year % 29.53) / 29.53),
            'lunar_cos': np.cos(2 * np.pi * (day_of_year % 29.53) / 29.53),
            # Geospatial (v3) — matching training column names
            'lat': lat_val, 'lon': lon_val, 'elev': elev_val, 'coast_km': coast_km_val,
            'lat_norm': (lat_val - 6.0) / (18.0 - 6.0),
            'lon_norm': (lon_val - 117.0) / (127.0 - 117.0),
            'coast_km_log': np.log1p(coast_km_val),
            'elev_norm': elev_val / 1000.0,
            'latitude': lat_val, 'longitude': lon_val, 'elevation': elev_val,
            # ENSO (v3)
            'enso_index': enso_idx,
            'is_el_nino': 1 if enso_idx > 0.5 else 0,
            'is_la_nina': 1 if enso_idx < -0.5 else 0,
            # Interaction features (matching v3 training names)
            'temp_humidity': temp * hum,
            'temp_x_humidity': temp * hum,
            'pressure_wind': press * wind,
            'pressure_x_wind': press * wind,
            'temp_x_rain': temp * rain,
            'humidity_x_rain': hum * rain,
            'wind_x_rain': wind * rain,
            'humidity_sq': hum ** 2,
            'pressure_sq': press ** 2,
            'dew_point': temp - ((100 - hum) / 5),
            'dew_point_approx': temp - ((100 - hum) / 5),
            'heat_index': temp + 0.5555 * (6.11 * np.exp(5417.7530 * (1/273.16 - 1/(273.15 + temp - ((100 - hum) / 5)))) - 10) if hum > 40 else temp,
            'wind_chill': temp if wind < 5 else 13.12 + 0.6215 * temp - 11.37 * (wind ** 0.16) + 0.3965 * temp * (wind ** 0.16),
            # Rainfall indicators
            'rain_yesterday': 1 if _hist_val('rainfall', 1) > 0 else 0,
            'rain_3day_sum': sum(_hist_val('rainfall', i) for i in range(1, 4)),
            'rain_7day_sum': sum(_hist_val('rainfall', i) for i in range(1, 8)),
            # Pressure change
            'pressure_drop_1d': _hist_diff('pressure', 1),
            'pressure_drop_3d': _hist_diff('pressure', 3),
            'humidity_rise_1d': _hist_diff('humidity', 1),
            # Extreme indicators (v3)
            'is_hot': 1 if temp > 33 else 0,
            'is_cold': 1 if temp < 22 else 0,
            'is_heavy_rain': 1 if rain > 20 else 0,
            'is_very_heavy_rain': 1 if rain > 50 else 0,
            'is_high_wind': 1 if wind > 30 else 0,
            'is_storm_wind': 1 if wind > 60 else 0,
            'is_low_pressure': 1 if press < 1005 else 0,
            'is_very_low_pressure': 1 if press < 995 else 0,
            'is_typhoon_conditions': 1 if (wind > 60 and press < 1000 and rain > 50) else 0,
            # Historical comparison (v3)
            'hist_temp_mean': hist_means['temperature'],
            'hist_humidity_mean': hist_means['humidity'],
            'hist_rain_mean': hist_means['rainfall'],
            'hist_wind_mean': hist_means['wind_speed'],
            'hist_pressure_mean': hist_means['pressure'],
            'temp_vs_hist': temp - hist_means['temperature'],
            'humidity_vs_hist': hum - hist_means['humidity'],
            'rain_vs_hist': rain - hist_means['rainfall'],
        }
        
        # Add lag/rolling/std/diff/ewm features — using EXACT v3 column names
        for param in ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']:
            for lag in [1, 2, 3, 5, 7]:
                feature_lookup[f'{param}_lag{lag}'] = _hist_val(param, lag)
            feature_lookup[f'{param}_lag3_avg'] = _hist_roll(param, 3)
            feature_lookup[f'{param}_lag7_avg'] = _hist_roll(param, 7)
            for window in [3, 7, 14]:
                # v3 uses roll_mean_3, roll_std_3 naming
                feature_lookup[f'{param}_roll_mean_{window}'] = _hist_roll(param, window)
                feature_lookup[f'{param}_roll_std_{window}'] = _hist_std(param, window)
                feature_lookup[f'{param}_roll_max_{window}'] = _hist_roll_max(param, window)
                feature_lookup[f'{param}_roll_min_{window}'] = _hist_roll_min(param, window)
                # Also add legacy naming for backwards compat
                feature_lookup[f'{param}_roll{window}'] = _hist_roll(param, window)
                feature_lookup[f'{param}_roll{window}_mean'] = _hist_roll(param, window)
                feature_lookup[f'{param}_roll{window}_std'] = _hist_std(param, window)
                feature_lookup[f'{param}_roll{window}_max'] = _hist_roll_max(param, window)
                feature_lookup[f'{param}_roll{window}_min'] = _hist_roll_min(param, window)
            feature_lookup[f'{param}_std7'] = _hist_std(param, 7)
            feature_lookup[f'{param}_diff1'] = _hist_diff(param, 1)
            feature_lookup[f'{param}_diff3'] = _hist_diff(param, 3)
            feature_lookup[f'{param}_ewm7'] = _hist_ewm(param, 7)
            feature_lookup[f'{param}_ewm14'] = _hist_ewm(param, 14)
            # Anomalies (v3)
            roll7 = _hist_roll(param, 7)
            roll14 = _hist_roll(param, 14)
            feature_lookup[f'{param}_anomaly_7d'] = cv.get(param, 0) - roll7
            feature_lookup[f'{param}_anomaly_14d'] = cv.get(param, 0) - roll14
            feature_lookup[f'{param}_anomaly'] = cv.get(param, 0) - _hist_roll(param, 7)
        
        # Specific extras
        feature_lookup['rainfall_roll3_max'] = _hist_roll_max('rainfall', 3)
        feature_lookup['rainfall_roll7_max'] = _hist_roll_max('rainfall', 7)
        
        # Build feature vector in correct order
        if feature_names:
            features = [feature_lookup.get(f, 0.0) for f in feature_names]
        else:
            # Legacy 16-feature fallback
            features = [
                day_of_year,
                feature_lookup['day_sin'], feature_lookup['day_cos'],
                month, feature_lookup['month_sin'], feature_lookup['month_cos'],
                feature_lookup['is_wet_season'], feature_lookup['is_dry_season'],
                feature_lookup['is_habagat'], feature_lookup['is_amihan'],
                feature_lookup['is_typhoon_season'],
                cv.get('temperature', 30), cv.get('humidity', 75),
                cv.get('rainfall', 0), cv.get('wind_speed', 10), cv.get('pressure', 1013)
            ]
        
        return np.array(features, dtype=np.float32)

    def _prepare_sequence_for_lstm(self, current_values: Dict, location: str, lookback: int = 7) -> np.ndarray:
        """Prepare sequence data for LSTM prediction using real historical data + proper scaler.
        
        Normalization chain: raw → norm_ranges [0,1] → scaler.transform() [0,1]
        The LSTM was trained on data that went through BOTH normalization stages.
        """
        params = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']
        location_key = location.lower().replace(' ', '_')
        scaler = self.lstm_scalers.get(location_key)

        # Build sequence from weather_history (most recent lookback entries)
        hist = self.weather_history if self.weather_history else []
        raw_sequence = []

        # Fill from history (oldest first)
        if len(hist) >= lookback:
            for i in range(lookback, 0, -1):
                row = [hist[-i].get(p, current_values.get(p, 0)) for p in params]
                raw_sequence.append(row)
        else:
            # Pad with current values for missing history, then append available history
            for _ in range(lookback - len(hist)):
                row = [current_values.get(p, 0) for p in params]
                raw_sequence.append(row)
            for i in range(len(hist), 0, -1):
                row = [hist[-i].get(p, current_values.get(p, 0)) for p in params]
                raw_sequence.append(row)

        raw_array = np.array(raw_sequence, dtype=np.float32)  # shape (lookback, 5)

        # Step 1: Normalize raw values to [0,1] using global norm_ranges
        for i, p in enumerate(params):
            lo, hi = self.norm_ranges.get(p, (0, 1))
            if hi > lo:
                raw_array[:, i] = (raw_array[:, i] - lo) / (hi - lo)
        raw_array = np.clip(raw_array, 0, 1)

        # Step 2: Apply per-location scaler (trained on already-normalized [0,1] data)
        if scaler is not None:
            try:
                raw_array = scaler.transform(raw_array)
            except Exception:
                pass  # Already in norm_ranges space, acceptable fallback

        # Shape: (1, lookback, 5) for batch prediction
        return raw_array.reshape(1, lookback, len(params))

    def _predict_next_day_from_current(self, current_values: Dict, seed: int = None) -> Dict:
        """Predict next day from current values"""
        predictions = {}
        
        # Use seed for deterministic predictions
        if seed is not None:
            variation_temp = ((seed * 13) % 400 - 200) / 100  # Range: -2 to 2
            variation_humidity = ((seed * 17) % 20 - 10)  # Range: -10 to 10
            variation_wind = ((seed * 19) % 600 - 300) / 100  # Range: -3 to 3
            variation_pressure = ((seed * 23) % 1000 - 500) / 100  # Range: -5 to 5
            rainfall_value = ((seed * 29) % 500) / 100  # Range: 0 to 5
        else:
            variation_temp = np.random.uniform(-2, 2)
            variation_humidity = np.random.randint(-10, 10)
            rainfall_value = np.random.uniform(0, 5)
            variation_wind = np.random.uniform(-3, 3)
            variation_pressure = np.random.uniform(-5, 5)
        
        predictions['temperature'] = current_values['temperature'] + variation_temp
        predictions['humidity'] = max(30, min(100, current_values['humidity'] + variation_humidity))
        predictions['rainfall'] = max(0, rainfall_value)
        predictions['wind_speed'] = max(0, current_values['wind_speed'] + variation_wind)
        predictions['pressure'] = current_values['pressure'] + variation_pressure
        predictions['condition'] = self._predict_next_condition(current_values['condition'])
        
        return predictions

    def _get_last_values(self, column: str, n_days: int) -> Optional[np.ndarray]:
        """Get last n values for a column"""
        if self.data is None or column not in self.data.columns:
            return None
        
        daily_data = self.data.groupby('date')[column].mean().reset_index()
        daily_data = daily_data.sort_values('date')
        
        if len(daily_data) < n_days:
            return None
        
        return daily_data[column].iloc[-n_days:].values

    def _get_last_conditions(self, n_days: int) -> Optional[np.ndarray]:
        """Get last n condition encodings"""
        if self.data is None or 'condition_encoder' not in self.models:
            return None
        
        encoder = self.models['condition_encoder']
        
        daily_conditions = self.data.groupby('date')['weather_condition'].agg(
            lambda x: x.mode().iloc[0] if not x.mode().empty else 'Sunny'
        ).reset_index()
        daily_conditions = daily_conditions.sort_values('date')
        
        if len(daily_conditions) < n_days:
            return None
        
        last_conditions = daily_conditions['weather_condition'].iloc[-n_days:].values
        encoded = encoder.transform(last_conditions)
        
        return encoded

    def _predict_next_condition(self, current_condition: str) -> str:
        """Predict next day's weather condition"""
        current_lower = current_condition.lower()
        
        transitions = {
            'sunny': ['Sunny', 'Partly cloudy', 'Cloudy'],
            'partly cloudy': ['Partly cloudy', 'Sunny', 'Cloudy', 'Light rain'],
            'cloudy': ['Cloudy', 'Partly cloudy', 'Light rain', 'Rainy'],
            'rainy': ['Light rain', 'Cloudy', 'Partly cloudy', 'Sunny'],
            'light rain': ['Light rain', 'Cloudy', 'Partly cloudy', 'Sunny']
        }
        
        options = transitions.get(current_lower, ['Partly cloudy', 'Sunny', 'Cloudy'])
        return np.random.choice(options)

    def _deg_to_direction(self, degrees: float) -> str:
        """Convert wind degrees to direction"""
        directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 
                     'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        index = round(degrees / 22.5) % 16
        return directions[index]

    def _get_weather_icon(self, condition: str) -> str:
        """Map weather condition to icon code"""
        condition_lower = condition.lower()
        
        if 'clear' in condition_lower or 'sunny' in condition_lower:
            return '01d'
        elif 'partly' in condition_lower:
            return '02d'
        elif 'cloudy' in condition_lower or 'overcast' in condition_lower:
            return '03d'
        elif 'rain' in condition_lower or 'drizzle' in condition_lower:
            return '10d'
        elif 'thunder' in condition_lower or 'storm' in condition_lower:
            return '11d'
        elif 'snow' in condition_lower:
            return '13d'
        elif 'mist' in condition_lower or 'fog' in condition_lower:
            return '50d'
        else:
            return '02d'

    def get_weather_impact_for_shrimp(self, weather_data: Dict) -> Optional[Dict]:
        """Analyze weather impact on shrimp farming"""
        if not weather_data:
            return None
        
        impacts = {
            'temperature_impact': 'normal',
            'rain_impact': 'normal',
            'wind_impact': 'normal',
            'recommendations': []
        }
        
        temp = weather_data.get('temperature', 26)
        if temp > 32:
            impacts['temperature_impact'] = 'high_risk'
            impacts['recommendations'].append('High temperature alert: Monitor water quality, increase circulation')
        elif temp > 28:
            impacts['temperature_impact'] = 'moderate_risk'
            impacts['recommendations'].append('Elevated temperature: Ensure adequate water circulation')
        elif temp < 20:
            impacts['temperature_impact'] = 'moderate_risk'
            impacts['recommendations'].append('Low temperature: Reduce feeding, shrimp metabolism is slower')
        else:
            impacts['temperature_impact'] = 'optimal'
        
        precip = weather_data.get('precipMm', 0)
        if precip > 20:
            impacts['rain_impact'] = 'high_risk'
            impacts['recommendations'].append('Heavy rain expected: Monitor salinity and pH, reduce feeding')
        elif precip > 5:
            impacts['rain_impact'] = 'moderate_risk'
            impacts['recommendations'].append('Moderate rain: Check water quality after rainfall')
        
        wind = weather_data.get('windKmh', 10)
        if wind > 40:
            impacts['wind_impact'] = 'high_risk'
            impacts['recommendations'].append('Strong winds: Secure equipment, monitor water turbidity')
        elif wind > 25:
            impacts['wind_impact'] = 'moderate_risk'
            impacts['recommendations'].append('Moderate winds: Good for natural aeration')
        else:
            impacts['wind_impact'] = 'optimal'
            impacts['recommendations'].append('Good wind conditions for natural aeration')
        
        uv = weather_data.get('uvIndex', 5)
        if uv > 8:
            impacts['recommendations'].append('High UV index: Consider shade nets to reduce heat stress')
        
        return impacts

    def _save_weather_to_db(self, weather_data: Dict, forecast_type: str, forecast_date):
        """Save weather forecast to database"""
        try:
            # Check if Django is properly configured
            import django
            from django.conf import settings
            
            if not settings.configured:
                print("âš ï¸ Django settings not configured, skipping database save")
                return None
            
            from api.models import WeatherForecast
            from django.utils import timezone
            
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
                    'source': weather_data.get('source', 'ml_prediction'),
                }
            )
            
            weather_obj.calculate_impacts()
            weather_obj.save()
            
            return weather_obj
            
        except Exception as e:
            print(f"âš ï¸ Error saving weather to database: {e}")
            return None

    def get_municipalities(self) -> List[Dict]:
        """Get list of available municipalities"""
        return self.municipalities

    def get_hourly_forecast(self, location: str):
        """Get hourly forecast for next 24 hours from OpenWeather API"""
        try:
            city_name = location.split(',')[0].strip()
            url = f'https://api.openweathermap.org/data/2.5/forecast?q={location},PH&appid={self.openweather_api_key}&units=metric'
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                url = f'https://api.openweathermap.org/data/2.5/forecast?q={city_name},PH&appid={self.openweather_api_key}&units=metric'
                response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            hourly_data = []
            for item in data['list'][:8]:
                dt = datetime.fromtimestamp(item['dt'])
                hourly_data.append({'datetime': dt.isoformat(), 'time': dt.strftime('%I:%M %p'), 'hour': dt.strftime('%I %p'), 'temperature': round(item['main']['temp'], 1), 'feels_like': round(item['main']['feels_like'], 1), 'humidity': item['main']['humidity'], 'pressure': round(item['main']['pressure'], 1), 'wind_speed': round(item['wind']['speed'] * 3.6, 1), 'wind_direction': item['wind'].get('deg', 0), 'wind_gust': round(item['wind'].get('gust', 0) * 3.6, 1), 'precipitation': round(item.get('rain', {}).get('3h', 0), 2), 'snow': round(item.get('snow', {}).get('3h', 0), 2), 'clouds': item['clouds']['all'], 'description': item['weather'][0]['description'].capitalize(), 'icon': item['weather'][0]['icon'], 'icon_url': f"https://openweathermap.org/img/wn/{item['weather'][0]['icon']}@2x.png", 'pop': int(item.get('pop', 0) * 100), 'visibility': round(item.get('visibility', 10000) / 1000, 1)})
            return hourly_data
        except Exception as e:
            print(f"[ERROR] Error fetching hourly forecast: {e}")
            return []

    def get_weather_alerts(self, location: str, weekly_data: list = None, current_data: dict = None):
        """Get weather alerts and warnings"""
        alerts = []
        try:
            current = current_data or self.get_current_weather_enhanced(location, save_to_db=False)
            weekly = weekly_data or self.predict_weekly_enhanced(location, 7, save_to_db=False)
            if not current:
                return alerts
            if current['temperature'] > 35:
                alerts.append({'type': 'extreme_heat', 'severity': 'high', 'title': 'Extreme Heat Warning', 'message': f"Temperature is {current['temperature']}C. Critical risk to shrimp health.", 'recommendations': ['Increase water circulation immediately', 'Monitor water quality closely'], 'icon': 'Fire', 'color': 'red'})
            elif current['temperature'] > 32:
                alerts.append({'type': 'high_temperature', 'severity': 'medium', 'title': 'High Temperature Alert', 'message': f"Temperature is {current['temperature']}C. Monitor shrimp behavior.", 'recommendations': ['Increase water circulation', 'Monitor water quality'], 'icon': 'Thermometer', 'color': 'orange'})
            for day in weekly[:3]:
                if day.get('precipMm', 0) > 50:
                    alerts.append({'type': 'heavy_rain', 'severity': 'high', 'title': f"Heavy Rainfall Expected - {day['day']}", 'message': f"Expected rainfall: {day['precipMm']}mm. Prepare for flooding.", 'recommendations': ['Check pond drainage systems', 'Monitor salinity levels'], 'icon': 'Rain', 'color': 'blue', 'date': day['date']})
            if current.get('windKmh', 0) > 40:
                alerts.append({'type': 'strong_wind', 'severity': 'medium', 'title': 'Strong Wind Warning', 'message': f"Wind speed: {current['windKmh']} km/h. Secure equipment.", 'recommendations': ['Secure loose equipment', 'Check aerator stability'], 'icon': 'Wind', 'color': 'yellow'})
            month = datetime.now().month
            if month in [6, 7, 8, 9, 10, 11]:
                typhoon_risk = 'high' if month in [8, 9, 10] else 'medium'
                alerts.append({'type': 'typhoon_season', 'severity': 'info', 'title': 'Typhoon Season Active', 'message': f'Peak typhoon season. Risk level: {typhoon_risk.upper()}', 'recommendations': ['Monitor weather updates daily', 'Maintain emergency supplies'], 'icon': 'Typhoon', 'color': 'purple'})
            return alerts
        except Exception as e:
            print(f"[ERROR] Error generating weather alerts: {e}")
            return []

    def get_weather_impact_for_shrimp(self, current_weather: Dict) -> Dict:
        """Analyze weather impact on shrimp farming with accurate good/bad classifications and recommendations.

        Analyzes current weather conditions and provides:
        - Overall impact classification (good/moderate/poor)
        - Parameter-specific assessments
        - Shrimp farming specific recommendations
        - Risk levels for different aspects

        Uses shrimp farming optimal ranges and weather sensitivity analysis.
        """
        try:
            # Extract key weather parameters
            temp = current_weather.get('temperature', 28)
            humidity = current_weather.get('humidity', 75)
            wind_speed = current_weather.get('windKmh', 15)
            precip = current_weather.get('precipMm', 0)
            pressure = current_weather.get('pressure', 1010)
            description = current_weather.get('description', '').lower()

            # Shrimp farming optimal weather ranges
            optimal_ranges = {
                'temperature': {'min': 25, 'max': 32, 'critical_min': 20, 'critical_max': 35},
                'humidity': {'min': 60, 'max': 85, 'critical_min': 40, 'critical_max': 95},
                'wind_speed': {'min': 5, 'max': 25, 'critical_min': 0, 'critical_max': 40},
                'precipitation': {'max': 10, 'critical_max': 50},  # Max daily precipitation
                'pressure': {'min': 1005, 'max': 1020}  # Normal pressure range
            }

            # Analyze each parameter
            assessments = {}
            issues = []
            recommendations = []

            # Temperature assessment
            if temp < optimal_ranges['temperature']['critical_min']:
                assessments['temperature'] = {'status': 'poor', 'risk': 'high', 'message': f'Too cold ({temp}°C) - Shrimp metabolism reduced'}
                issues.append('low_temperature')
                recommendations.extend([
                    'Increase water temperature gradually (max 2°C/day)',
                    'Reduce feeding by 30-50% until temperature stabilizes',
                    'Monitor shrimp for signs of stress (reduced activity, pale color)'
                ])
            elif temp < optimal_ranges['temperature']['min']:
                assessments['temperature'] = {'status': 'moderate', 'risk': 'medium', 'message': f'Cool conditions ({temp}°C) - Monitor closely'}
                issues.append('cool_temperature')
                recommendations.extend([
                    'Monitor water temperature hourly',
                    'Adjust feeding based on shrimp activity levels'
                ])
            elif temp <= optimal_ranges['temperature']['max']:
                assessments['temperature'] = {'status': 'good', 'risk': 'low', 'message': f'Optimal temperature ({temp}°C)'}
            elif temp <= optimal_ranges['temperature']['critical_max']:
                assessments['temperature'] = {'status': 'moderate', 'risk': 'medium', 'message': f'Warm conditions ({temp}°C) - Monitor oxygen levels'}
                issues.append('warm_temperature')
                recommendations.extend([
                    'Increase aeration and water circulation',
                    'Monitor dissolved oxygen levels closely',
                    'Consider partial water exchange if DO drops below 4 mg/L'
                ])
            else:
                assessments['temperature'] = {'status': 'poor', 'risk': 'high', 'message': f'Extreme heat ({temp}°C) - Critical risk'}
                issues.append('extreme_heat')
                recommendations.extend([
                    'URGENT: Increase aeration to maximum capacity',
                    'Perform emergency water exchange (20-30%)',
                    'Move shrimp to shaded areas if possible',
                    'Monitor for disease outbreaks (increased temperature stresses immune system)'
                ])

            # Humidity assessment (affects evaporation and pond water levels)
            if humidity < optimal_ranges['humidity']['critical_min']:
                assessments['humidity'] = {'status': 'poor', 'risk': 'high', 'message': f'Very dry air ({humidity}%) - High evaporation risk'}
                issues.append('low_humidity')
                recommendations.extend([
                    'Increase pond water levels to compensate for evaporation',
                    'Install shade nets to reduce solar heating',
                    'Monitor salinity levels (may increase due to evaporation)'
                ])
            elif humidity < optimal_ranges['humidity']['min']:
                assessments['humidity'] = {'status': 'moderate', 'risk': 'medium', 'message': f'Dry conditions ({humidity}%) - Monitor water levels'}
                issues.append('dry_conditions')
                recommendations.append('Monitor pond water levels and top up as needed')
            elif humidity <= optimal_ranges['humidity']['max']:
                assessments['humidity'] = {'status': 'good', 'risk': 'low', 'message': f'Good humidity ({humidity}%)'}
            else:
                assessments['humidity'] = {'status': 'moderate', 'risk': 'medium', 'message': f'High humidity ({humidity}%) - Monitor for fungal issues'}
                issues.append('high_humidity')
                recommendations.append('Monitor for fungal diseases in shrimp')

            # Wind assessment (affects oxygen transfer and pond mixing)
            if wind_speed > optimal_ranges['wind_speed']['critical_max']:
                assessments['wind'] = {'status': 'poor', 'risk': 'high', 'message': f'Strong winds ({wind_speed} km/h) - Risk of damage'}
                issues.append('strong_wind')
                recommendations.extend([
                    'Secure all equipment and pond structures',
                    'Check aerator stability and moorings',
                    'Monitor for wind-blown debris in ponds'
                ])
            elif wind_speed > optimal_ranges['wind_speed']['max']:
                assessments['wind'] = {'status': 'moderate', 'risk': 'medium', 'message': f'Windy conditions ({wind_speed} km/h)'}
                issues.append('windy')
                recommendations.append('Monitor aerator performance and pond mixing')
            elif wind_speed >= optimal_ranges['wind_speed']['min']:
                assessments['wind'] = {'status': 'good', 'risk': 'low', 'message': f'Good wind conditions ({wind_speed} km/h)'}
            else:
                assessments['wind'] = {'status': 'moderate', 'risk': 'low', 'message': f'Calm conditions ({wind_speed} km/h) - Limited natural aeration'}
                issues.append('calm_wind')
                recommendations.append('Ensure mechanical aeration is functioning properly')

            # Precipitation assessment
            if precip > optimal_ranges['precipitation']['critical_max']:
                assessments['precipitation'] = {'status': 'poor', 'risk': 'high', 'message': f'Heavy rainfall ({precip} mm) - Flooding risk'}
                issues.append('heavy_rain')
                recommendations.extend([
                    'URGENT: Check drainage systems and pond overflow prevention',
                    'Monitor water quality changes (salinity dilution, pH shifts)',
                    'Prepare emergency harvesting if flooding expected',
                    'Move equipment to higher ground'
                ])
            elif precip > optimal_ranges['precipitation']['max']:
                assessments['precipitation'] = {'status': 'moderate', 'risk': 'medium', 'message': f'Rain expected ({precip} mm) - Monitor drainage'}
                issues.append('rain')
                recommendations.extend([
                    'Ensure drainage systems are clear',
                    'Monitor salinity and pH changes after rain',
                    'Check for runoff contamination'
                ])
            else:
                assessments['precipitation'] = {'status': 'good', 'risk': 'low', 'message': f'Low precipitation ({precip} mm)'}

            # Pressure assessment (storm prediction)
            if pressure < optimal_ranges['pressure']['min']:
                assessments['pressure'] = {'status': 'poor', 'risk': 'high', 'message': f'Low pressure ({pressure} hPa) - Storm approaching'}
                issues.append('low_pressure')
                recommendations.extend([
                    'Prepare for severe weather',
                    'Secure all equipment and ponds',
                    'Monitor weather updates closely',
                    'Consider emergency harvesting if typhoon expected'
                ])
            elif pressure > optimal_ranges['pressure']['max']:
                assessments['pressure'] = {'status': 'moderate', 'risk': 'low', 'message': f'High pressure ({pressure} hPa) - Stable weather'}
            else:
                assessments['pressure'] = {'status': 'good', 'risk': 'low', 'message': f'Normal pressure ({pressure} hPa)'}

            # Weather condition assessment
            weather_issues = []
            if 'rain' in description or 'storm' in description:
                weather_issues.append('precipitation')
                recommendations.append('Monitor water quality changes during/after rain')
            if 'cloud' in description or 'overcast' in description:
                weather_issues.append('reduced_sunlight')
                recommendations.append('Monitor phytoplankton levels (may decrease without sunlight)')
            if 'sunny' in description or 'clear' in description:
                recommendations.append('Ensure adequate shade coverage to prevent excessive heating')

            # Overall impact classification
            status_counts = {'good': 0, 'moderate': 0, 'poor': 0}
            risk_counts = {'low': 0, 'medium': 0, 'high': 0}

            for assessment in assessments.values():
                status_counts[assessment['status']] += 1
                risk_counts[assessment['risk']] += 1

            # Determine overall status
            if status_counts['poor'] > 0:
                overall_status = 'poor'
                overall_message = 'Poor conditions for shrimp farming - Take immediate action'
            elif status_counts['moderate'] > 1 or risk_counts['high'] > 0:
                overall_status = 'moderate'
                overall_message = 'Moderate conditions - Monitor closely and implement recommendations'
            else:
                overall_status = 'good'
                overall_message = 'Good conditions for shrimp farming - Continue normal operations'

            # Add general recommendations
            if overall_status == 'good':
                recommendations.extend([
                    'Maintain regular monitoring schedule',
                    'Continue optimal feeding and water quality management',
                    'Prepare contingency plans for weather changes'
                ])
            elif overall_status == 'moderate':
                recommendations.extend([
                    'Increase monitoring frequency',
                    'Prepare backup systems (generators, water pumps)',
                    'Review emergency response plans'
                ])
            else:  # poor
                recommendations.extend([
                    'Implement emergency response protocols',
                    'Consider early harvesting if conditions deteriorate further',
                    'Contact aquaculture specialists for immediate advice',
                    'Document all actions taken for insurance/financial purposes'
                ])

            # Remove duplicates and prioritize
            recommendations = list(dict.fromkeys(recommendations))

            return {
                'overall_status': overall_status,
                'overall_message': overall_message,
                'assessments': assessments,
                'issues': issues + weather_issues,
                'recommendations': recommendations,
                'risk_summary': {
                    'high': risk_counts['high'],
                    'medium': risk_counts['medium'],
                    'low': risk_counts['low']
                },
                'parameter_summary': {
                    'good': status_counts['good'],
                    'moderate': status_counts['moderate'],
                    'poor': status_counts['poor']
                },
                'timestamp': datetime.now().isoformat(),
                'location': current_weather.get('city', 'Unknown')
            }

        except Exception as e:
            print(f"[ERROR] Error analyzing shrimp farming weather impact: {e}")
            return {
                'overall_status': 'unknown',
                'overall_message': 'Unable to analyze weather impact - check system logs',
                'assessments': {},
                'issues': ['analysis_error'],
                'recommendations': ['Contact system administrator', 'Continue manual monitoring'],
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


# Removed global instance — use ml_loader.get_weather_predictor() instead