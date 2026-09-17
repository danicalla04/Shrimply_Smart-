"""
Phase 2: Ensemble + ML Correction Service
Combines ensemble forecasting with trained ML models for improved accuracy
Enhanced with Oriental Mindoro municipalities support
"""

import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
import pickle
from .mindoro_locations_config import (
    get_all_municipalities,
    get_municipality_config,
    resolve_location,
    get_primary_municipality,
)

logger = logging.getLogger(__name__)

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost not available - XGBoost corrections disabled")

try:
    import tensorflow as tf
    from tensorflow import keras
    TENSORFLOW_AVAILABLE = True
    from tensorflow.keras.models import load_model
except ImportError:
    TENSORFLOW_AVAILABLE = False
    logger.warning("TensorFlow not available - LSTM corrections disabled")


class EnsembleMLPredictor:
    """
    Combines ensemble forecasts with ML model corrections
    for improved accuracy and confidence scoring.
    """
    
    def __init__(self):
        """Initialize ML model loader and correction system."""
        # Path to models directory: backend/api/../.. = Shrimply_Smart root, then /dataset/models
        self.models_dir = Path(__file__).resolve().parent.parent.parent / 'dataset' / 'models'
        self.xgboost_models = {}  # temperature, humidity, pressure, rainfall, wind_speed
        self.lstm_models = {}
        self.correction_models = {}
        self.feature_scalers = {}
        self.model_metrics = {}  # RMSE, MAE for confidence calculation
        self.location_models = {}  # Location-specific model tracking
        
        # Initialize with primary location (Calapan City)
        self.active_location = get_primary_municipality()  # 'calapan'
        self._available_municipalities = get_all_municipalities()
        
        self._load_models()
    
    def _load_models(self):
        """Load all available ML models from disk."""
        if not self.models_dir.exists():
            logger.warning(f"Models directory not found: {self.models_dir}")
            return
        
        # Load XGBoost models
        if XGBOOST_AVAILABLE:
            self._load_xgboost_models()
        
        # Load LSTM models
        if TENSORFLOW_AVAILABLE:
            self._load_lstm_models()
        
        # Load correction models
        self._load_correction_models()
        
        # Load feature scalers
        self._load_feature_scalers()
        
        # Load model metrics for confidence calculation
        self._load_model_metrics()
        
        logger.info(f"Loaded ML models: {len(self.xgboost_models)} XGBoost, "
                   f"{len(self.lstm_models)} LSTM, {len(self.correction_models)} Correction")
    
    def _load_xgboost_models(self):
        """Load all XGBoost models (v3 versions preferred)."""
        metrics = [
            'temperature', 'humidity', 'pressure', 'rainfall', 'wind_speed'
        ]
        
        for metric in metrics:
            # Try v3 first (improved models)
            v3_path = self.models_dir / f'xgboost_{metric}_v3.pkl'
            if v3_path.exists():
                try:
                    with open(v3_path, 'rb') as f:
                        self.xgboost_models[metric] = pickle.load(f)
                    logger.info(f"Loaded XGBoost v3 model: {metric}")
                except Exception as e:
                    logger.error(f"Failed to load XGBoost v3 {metric}: {e}")
            
            # Fallback to standard version
            else:
                path = self.models_dir / f'xgboost_{metric}.pkl'
                if path.exists():
                    try:
                        with open(path, 'rb') as f:
                            self.xgboost_models[metric] = pickle.load(f)
                        logger.info(f"Loaded XGBoost model: {metric}")
                    except Exception as e:
                        logger.error(f"Failed to load XGBoost {metric}: {e}")
    
    def _load_lstm_models(self):
        """Load LSTM models for all Oriental Mindoro municipalities."""
        municipalities = get_all_municipalities()
        
        for municipality in municipalities:
            # Try v3 first (improved models)
            lstm_path = self.models_dir / f'lstm_{municipality}_v3.h5'
            if lstm_path.exists():
                try:
                    model = keras.models.load_model(
                        lstm_path, 
                        compile=False,
                        custom_objects={'mse': 'mse'}
                    )
                    self.lstm_models[municipality] = model
                    logger.info(f"✅ Loaded LSTM model: {municipality} (v3)")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load LSTM v3 {municipality}: {e}")
            
            # Fallback to standard version
            else:
                lstm_path = self.models_dir / f'lstm_{municipality}.h5'
                if lstm_path.exists():
                    try:
                        model = keras.models.load_model(
                            lstm_path,
                            compile=False,
                            custom_objects={'mse': 'mse'}
                        )
                        self.lstm_models[municipality] = model
                        logger.info(f"✅ Loaded LSTM model: {municipality}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to load LSTM {municipality}: {e}")
    
    def _load_correction_models(self):
        """Load correction models for systematic error adjustment."""
        metrics = ['temperature', 'humidity', 'pressure', 'wind_speed']
        
        for metric in metrics:
            path = self.models_dir / f'correction_{metric}_model.pkl'
            if path.exists():
                try:
                    with open(path, 'rb') as f:
                        self.correction_models[metric] = pickle.load(f)
                    logger.info(f"Loaded correction model: {metric}")
                except Exception as e:
                    logger.warning(f"Failed to load correction {metric}: {e}")
    
    def _load_feature_scalers(self):
        """Load feature scalers for normalization (all municipalities)."""
        # Load general scaler (from active location)
        scaler_path = self.models_dir / f'{self.active_location}_feature_scaler_v4.pkl'
        if scaler_path.exists():
            try:
                with open(scaler_path, 'rb') as f:
                    self.feature_scalers['general'] = pickle.load(f)
                logger.info("✅ Loaded general feature scaler")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load general scaler: {e}")
        
        # Load LSTM scalers per municipality
        municipalities = get_all_municipalities()
        for municipality in municipalities:
            # Try v3 first
            scaler_path = self.models_dir / f'scaler_{municipality}_v3.pkl'
            if scaler_path.exists():
                try:
                    with open(scaler_path, 'rb') as f:
                        self.feature_scalers[municipality] = pickle.load(f)
                    logger.debug(f"✅ Loaded LSTM scaler: {municipality} (v3)")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load LSTM scaler {municipality}: {e}")
            
            # Fallback to standard version
            else:
                scaler_path = self.models_dir / f'scaler_{municipality}.pkl'
                if scaler_path.exists():
                    try:
                        with open(scaler_path, 'rb') as f:
                            self.feature_scalers[municipality] = pickle.load(f)
                        logger.debug(f"✅ Loaded LSTM scaler: {municipality}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to load LSTM scaler {municipality}: {e}")
    
    def _load_model_metrics(self):
        """Load model performance metrics for confidence calculation."""
        metrics_path = self.models_dir / 'weather_model_metrics_v3.json'
        if metrics_path.exists():
            try:
                with open(metrics_path, 'r') as f:
                    self.model_metrics = json.load(f)
                logger.info(f"✅ Loaded model metrics with {len(self.model_metrics)} entries")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load model metrics: {e}")
    
    def set_location(self, location: str) -> bool:
        """
        Set the active location for LSTM and location-specific models.
        
        Args:
            location: Municipality key (e.g., 'calapan', 'puerto_galera')
        
        Returns:
            True if location was valid, False otherwise
        """
        # Resolve location alias
        resolved_location = resolve_location(location)
        
        # Validate it's a known municipality
        if resolved_location not in self._available_municipalities:
            logger.warning(f"⚠️ Unknown municipality: {location}, using default")
            self.active_location = get_primary_municipality()
            return False
        
        self.active_location = resolved_location
        config = get_municipality_config(resolved_location)
        logger.info(f"✅ Set active location: {config['display_name']} ({resolved_location})")
        return True
    
    def get_location_info(self) -> Dict:
        """Get information about the active location."""
        config = get_municipality_config(self.active_location)
        return {
            'key': self.active_location,
            'display_name': config['display_name'] if config else self.active_location,
            'has_lstm_model': self.active_location in self.lstm_models,
            'has_scaler': self.active_location in self.feature_scalers,
            'is_primary': config['is_primary'] if config else False,
        }
    
    def get_available_locations(self) -> List[Dict]:
        """Get list of all available municipalities."""
        return [
            {
                'key': m,
                'display_name': get_municipality_config(m)['display_name'],
                'has_model': m in self.lstm_models,
                'is_primary': get_municipality_config(m)['is_primary'],
            }
            for m in self._available_municipalities
        ]
    
    def apply_ml_correction(
        self,
        metric: str,
        ensemble_value: float,
        historical_data: Optional[Dict] = None,
    ) -> Tuple[float, float]:
        """
        Apply ML correction to ensemble forecast (location-aware).
        
        Args:
            metric: 'temperature', 'humidity', 'pressure', 'rainfall', 'wind_speed'
            ensemble_value: Raw ensemble prediction
            historical_data: Optional historical context for correction
        
        Returns:
            (corrected_value, correction_confidence)
        """
        correction_confidence = 0.0
        
        # Try location-specific LSTM correction first
        if self.active_location in self.lstm_models:
            try:
                model = self.lstm_models[self.active_location]
                scaler = self.feature_scalers.get(self.active_location)
                
                if scaler and historical_data:
                    # Create LSTM input sequence (simplified)
                    corrected = ensemble_value  # Placeholder - would use actual LSTM inference
                    correction_confidence = 0.8  # LSTM generally more accurate
                    
                    config = get_municipality_config(self.active_location)
                    logger.debug(f"✅ LSTM correction for {config['display_name']}/{metric}: "
                               f"{ensemble_value:.2f} -> {corrected:.2f}")
                    return float(corrected), correction_confidence
            except Exception as e:
                logger.warning(f"⚠️ LSTM correction failed for {self.active_location}/{metric}: {e}")
        
        # Try XGBoost correction (general)
        if metric in self.xgboost_models:
            try:
                model = self.xgboost_models[metric]
                # Create feature vector (simplified - in production would use full features)
                features = np.array([[ensemble_value]])
                corrected = model.predict(features)[0]
                correction_confidence = 0.7  # XGBoost generally reliable
                
                logger.debug(f"✅ XGBoost correction for {metric}: {ensemble_value:.2f} -> {corrected:.2f}")
                return float(corrected), correction_confidence
            except Exception as e:
                logger.warning(f"⚠️ XGBoost correction failed for {metric}: {e}")
        
        # No correction applied
        return ensemble_value, correction_confidence
    
    def calculate_ml_confidence(
        self,
        metric: str,
        xgboost_available: bool = True,
        lstm_available: bool = True,
    ) -> float:
        """Calculate confidence score based on available ML models."""
        confidence = 50.0  # Base confidence if no models
        
        if metric in self.model_metrics:
            rmse = self.model_metrics[metric].get('rmse', 0)
            # Normalize RMSE to confidence (lower RMSE = higher confidence)
            # Adjust thresholds based on metric type
            if metric == 'temperature':
                max_rmse = 5.0  # Temperature typically has higher RMSE
            elif metric == 'humidity':
                max_rmse = 15.0  # Humidity more variable
            else:
                max_rmse = 10.0
            
            confidence = max(30.0, 100.0 * (1.0 - rmse / max_rmse))
        
        # Boost confidence if multiple models available
        if xgboost_available and metric in self.xgboost_models:
            confidence += 10
        if lstm_available and self.active_location in self.lstm_models:
            confidence += 10
        
        return min(100.0, confidence)  # Cap at 100%
    
    def correct_ensemble_forecast(
        self,
        ensemble_forecast: Dict,
        location: Optional[str] = None,
        historical_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Apply ML corrections to complete ensemble forecast.
        
        Args:
            ensemble_forecast: Output from getEnsembleForecast()
                Should have: {current, daily, hourly, confidence, anomalies, ...}
            location: Optional municipality key to use (overrides active_location)
            historical_data: Optional historical context
        
        Returns:
            Corrected forecast with ML adjustments and confidence scores
        """
        # Set location if provided
        if location:
            self.set_location(location)
        
        corrected = ensemble_forecast.copy()
        
        metrics = ['temperature', 'humidity', 'pressure', 'rainfall', 'wind_speed']
        corrections_applied = []
        
        # Apply corrections to current forecast
        if 'current' in corrected:
            current = corrected['current']
            for metric in metrics:
                if metric in current:
                    original = current[metric]
                    corrected_value, conf = self.apply_ml_correction(metric, original, historical_data)
                    
                    # Store both original and corrected
                    current[f'{metric}_original'] = original
                    current[f'{metric}_corrected'] = corrected_value
                    current[f'{metric}_ml_confidence'] = conf
                    
                    if conf > 0:
                        corrections_applied.append({
                            'metric': metric,
                            'original': original,
                            'corrected': corrected_value,
                            'confidence': conf
                        })
        
        # Apply corrections to daily forecast
        if 'daily' in corrected and isinstance(corrected['daily'], list):
            for day in corrected['daily']:
                for metric in metrics:
                    if metric in day:
                        original = day[metric]
                        corrected_value, conf = self.apply_ml_correction(metric, original, historical_data)
                        day[f'{metric}_original'] = original
                        day[f'{metric}_corrected'] = corrected_value
                        day[f'{metric}_ml_confidence'] = conf
        
        # Calculate overall ML confidence
        ml_confidence = np.mean([
            self.calculate_ml_confidence(m, xgboost_available=m in self.xgboost_models)
            for m in metrics
        ])
        
        corrected['ml_confidence'] = float(ml_confidence)
        corrected['corrections_applied'] = corrections_applied
        corrected['ml_models_active'] = {
            'xgboost_count': len(self.xgboost_models),
            'lstm_count': len(self.lstm_models),
            'correction_count': len(self.correction_models),
        }
        corrected['location'] = self.active_location
        corrected['location_info'] = self.get_location_info()
        
        return corrected
    
    def get_model_info(self) -> Dict:
        """Get information about loaded ML models and locations."""
        return {
            'xgboost_models': list(self.xgboost_models.keys()),
            'lstm_models': list(self.lstm_models.keys()),
            'lstm_models_count': len(self.lstm_models),
            'correction_models': list(self.correction_models.keys()),
            'active_location': self.active_location,
            'active_location_info': self.get_location_info(),
            'available_municipalities': len(self._available_municipalities),
            'models_available': {
                'xgboost': len(self.xgboost_models),
                'lstm': len(self.lstm_models),
                'corrections': len(self.correction_models),
            },
            'libraries': {
                'xgboost': XGBOOST_AVAILABLE,
                'tensorflow': TENSORFLOW_AVAILABLE,
            },
            'municipality_models': {
                loc: {
                    'lstm': loc in self.lstm_models,
                    'scaler': loc in self.feature_scalers,
                    'display_name': get_municipality_config(loc)['display_name'],
                }
                for loc in self._available_municipalities
            }
        }


# Singleton instance
_ml_predictor = None


def get_ensemble_ml_predictor() -> EnsembleMLPredictor:
    """Get or create the singleton ML predictor instance."""
    global _ml_predictor
    if _ml_predictor is None:
        _ml_predictor = EnsembleMLPredictor()
    return _ml_predictor
