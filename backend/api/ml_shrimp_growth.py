"""
Machine Learning module for shrimp growth prediction.

This module handles:
- Data preprocessing for growth metrics
- Model training using Random Forest and LSTM
- Growth predictions
- Harvest date estimation
- AI recommendations
"""

import numpy as np
import pandas as pd
from datetime import timedelta
import json
import logging
from pathlib import Path
import pickle

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from tensorflow import keras
    from tensorflow.keras import layers, models
    import tensorflow as tf
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / 'ml_models'
MODEL_DIR.mkdir(exist_ok=True)


class GrowthDataPreprocessor:
    """Prepare growth metrics for model training."""
    
    @staticmethod
    def create_dataframe_from_metrics(metrics_qs):
        """
        Convert DailyGrowthMetric queryset to pandas DataFrame.
        
        Args:
            metrics_qs: QuerySet of DailyGrowthMetric objects
            
        Returns:
            DataFrame with engineered features
        """
        data = []
        for metric in metrics_qs.order_by('date'):
            data.append({
                'date': metric.date,
                'days_since_start': (metric.date - metrics_qs.first().date).days,
                'shrimp_count': metric.shrimp_count,
                'avg_weight': metric.avg_weight_grams,
                'daily_weight_gain': metric.daily_weight_gain_grams,
                'daily_mortality': metric.daily_mortality_percent,
                'feed_amount': metric.feed_amount_grams,
                'water_temp': metric.water_temperature or 25.0,
                'water_ph': metric.water_ph or 7.5,
                'dissolved_oxygen': metric.dissolved_oxygen or 6.0,
                'tds': metric.tds or 500.0,
                'is_rainy': 1 if metric.weather_condition and 'rain' in metric.weather_condition.lower() else 0,
                'notes': metric.notes,
            })
        
        if not data:
            return None
        
        df = pd.DataFrame(data)
        
        # Engineering features
        df['feed_per_shrimp'] = df['feed_amount'] / (df['shrimp_count'] + 1)
        df['weight_to_feed_ratio'] = df['avg_weight'] / (df['feed_amount'] + 0.1)
        df['survival_rate'] = (df['shrimp_count'] / df['shrimp_count'].iloc[0] * 100) if len(df) > 0 else 100
        df['cumulative_gain'] = df['daily_weight_gain'].cumsum()
        
        # Rolling averages
        df['temp_7day_avg'] = df['water_temp'].rolling(window=7, min_periods=1).mean()
        df['weight_7day_avg'] = df['avg_weight'].rolling(window=7, min_periods=1).mean()
        
        return df
    
    @staticmethod
    def prepare_training_data(season):
        """Prepare data for model training from a single season."""
        from .models import DailyGrowthMetric
        metrics_qs = DailyGrowthMetric.objects.filter(season=season).order_by('date')
        
        df = GrowthDataPreprocessor.create_dataframe_from_metrics(metrics_qs)
        if df is None or len(df) < 5:
            return None, None
        
        # Features for prediction
        feature_cols = [
            'days_since_start', 'daily_mortality', 'feed_amount', 'water_temp',
            'water_ph', 'dissolved_oxygen', 'tds', 'is_rainy', 'feed_per_shrimp',
            'weight_to_feed_ratio', 'survival_rate', 'temp_7day_avg'
        ]
        
        X = df[feature_cols].fillna(df[feature_cols].mean())
        y_weight = df['avg_weight'].values
        y_count = df['shrimp_count'].values
        
        return X, {'weight': y_weight, 'count': y_count}, df
    
    @staticmethod
    def normalize_features(X, scaler=None):
        """Normalize features."""
        if scaler is None:
            scaler = StandardScaler()
            X_normalized = scaler.fit_transform(X)
        else:
            X_normalized = scaler.transform(X)
        
        return X_normalized, scaler


class ShrimpGrowthPredictor:
    """ML model for predicting shrimp growth."""
    
    def __init__(self, model_name='growth_predictor_v1.pkl'):
        self.model_name = model_name
        self.model_path = MODEL_DIR / model_name
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.bundle = None
        self.model_family = None
        self.impute_medians = {}
        self.abw_curve_model = None
        self.abw_curve_features = None
        self.mean_adg = None
        self.load_model()
    
    def load_model(self):
        """Load trained model from disk."""
        self.bundle = None
        self.model_family = None
        self.impute_medians = {}
        self.abw_curve_model = None
        self.abw_curve_features = None
        self.mean_adg = None
        if self.model_path.exists():
            try:
                with open(self.model_path, 'rb') as f:
                    data = pickle.load(f)
                    self.bundle = data
                    self.model = data.get('model')
                    self.scaler = data.get('scaler')
                    self.feature_names = (
                        data.get('features')
                        or data.get('feature_names')
                    )
                    self.model_family = data.get('model_family')
                    self.impute_medians = data.get('impute_medians') or {}
                    self.abw_curve_model = data.get('abw_curve_model')
                    self.abw_curve_features = data.get('abw_curve_features')
                    self.mean_adg = data.get('mean_adg') or data.get('median_adg')
                logger.info(f'Loaded model from {self.model_path} ({self.model_family})')
                return True
            except Exception as e:
                logger.error(f'Failed to load model: {e}')
                return False
        return False
    
    def save_model(self):
        """Save trained model to disk."""
        try:
            with open(self.model_path, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'scaler': self.scaler,
                    'features': self.feature_names,
                }, f)
            logger.info(f'Saved model to {self.model_path}')
            return True
        except Exception as e:
            logger.error(f'Failed to save model: {e}')
            return False
    
    def train(self, X, y, test_size=0.2):
        """Train the model."""
        if not SKLEARN_AVAILABLE:
            logger.error('scikit-learn not available')
            return False
        
        try:
            X_normalized, scaler = GrowthDataPreprocessor.normalize_features(X)
            X_train, X_test, y_train, y_test = train_test_split(
                X_normalized, y, test_size=test_size, random_state=42
            )
            
            self.model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                random_state=42,
                n_jobs=-1,
            )
            self.model.fit(X_train, y_train)
            self.scaler = scaler
            self.feature_names = X.columns.tolist() if hasattr(X, 'columns') else None
            
            # Evaluate
            train_score = self.model.score(X_train, y_train)
            test_score = self.model.score(X_test, y_test)
            logger.info(f'Model trained: train_r2={train_score:.3f}, test_r2={test_score:.3f}')
            
            return True
        except Exception as e:
            logger.error(f'Training failed: {e}')
            return False
    
    def predict_weight(self, X):
        """Predict average shrimp weight."""
        if self.model is None:
            return None
        
        try:
            if self.scaler:
                X_normalized = self.scaler.transform(X)
            else:
                X_normalized = X
            
            prediction = self.model.predict(X_normalized)
            return np.clip(prediction, 0.1, 100)  # Reasonable bounds
        except Exception as e:
            logger.error(f'Prediction failed: {e}')
            return None
    
    def predict_harvest_date(self, current_date, current_weight, target_weight=18.0, days_ahead=60):
        """
        Estimate harvest date based on growth trajectory.
        
        Uses linear extrapolation from current growth rate.
        """
        if current_weight <= 0:
            return None
        
        # Simple linear growth model
        # Assume growth slows down as shrimp gets larger
        if current_weight < 5:
            daily_growth = 0.25  # grams/day for small shrimp
        elif current_weight < 10:
            daily_growth = 0.15
        else:
            daily_growth = 0.10
        
        remaining_growth = max(0, target_weight - current_weight)
        days_to_harvest = remaining_growth / daily_growth if daily_growth > 0 else 60
        
        estimated_harvest = current_date + timedelta(days=int(days_to_harvest))
        return estimated_harvest


def _predict_adg_sampling(predictor, season, latest_metric):
    """Predict ADG (g/day) from sampling-trained growth_predictor_v1.pkl."""
    bundle = predictor.bundle or {}
    feats = predictor.feature_names or [
        'doc', 'abw_g', 'lf_kg', 'initial_stock_pcs', 'sr_pct'
    ]
    medians = predictor.impute_medians or {}

    start = season.start_date
    doc = (latest_metric.date - start).days if start else 0
    doc = max(0, int(doc))

    current_weight = float(latest_metric.avg_weight_grams or 0)
    current_count = int(latest_metric.shrimp_count or 0) or 1
    initial_count = (
        getattr(season, 'initial_shrimp_quantity', 0)
        or season.stocking_density
        or current_count
    )
    feed_g = latest_metric.feed_amount_grams
    lf_kg = (float(feed_g) / 1000.0) if feed_g is not None else medians.get('lf_kg', 100.0)
    sr_pct = (current_count / initial_count * 100.0) if initial_count else medians.get('sr_pct', 80.0)

    feature_map = {
        'doc': float(doc),
        'abw_g': current_weight,
        'lf_kg': float(lf_kg),
        'initial_stock_pcs': float(initial_count),
        'sr_pct': float(sr_pct),
    }
    row = []
    for name in feats:
        val = feature_map.get(name)
        if val is None:
            val = medians.get(name, 0.0)
        row.append(float(val))

    X = np.array([row], dtype=float)
    try:
        import pandas as pd
        X = pd.DataFrame(X, columns=list(feats))
    except Exception:
        pass
    if predictor.scaler is not None and not hasattr(predictor.model, 'named_steps'):
        X = predictor.scaler.transform(X)
    adg = float(predictor.model.predict(X)[0])
    # Bound to biologically plausible shrimp ADG
    adg = float(np.clip(adg, 0.05, 1.2))
    model_version = bundle.get('model_version') or 'sampling-adg-v1'
    return adg, doc, model_version, feature_map


def _predict_adg_rrl(predictor, latest_metric):
    """Legacy RRL water-quality → SGR path."""
    feature_map = {
        'Temp': latest_metric.water_temperature,
        'Sal': None,
        'pH': latest_metric.water_ph,
        'DO': latest_metric.dissolved_oxygen,
        'TAN': None,
        'AL': None,
        'HN': None,
        'ORP': None,
        'Con': latest_metric.tds,
    }
    bundle = predictor.bundle or {}
    means = {
        'mean_sgr': bundle.get('mean_sgr'),
        'mean_lwg': bundle.get('mean_lwg'),
    }
    feats = predictor.feature_names or list(feature_map.keys())
    row = []
    defaults = {
        'Temp': 28.3, 'Sal': 13.4, 'pH': 8.47, 'DO': 5.2,
        'TAN': 0.35, 'AL': 175.0, 'HN': 205.0, 'ORP': 85.0, 'Con': 25.0,
    }
    for name in feats:
        val = feature_map.get(name)
        if val is None:
            val = defaults.get(name, 0.0)
        row.append(float(val))
    X = np.array([row])
    if predictor.scaler is not None:
        X = predictor.scaler.transform(X)
    predicted_sgr = float(predictor.model.predict(X)[0])
    mean_lwg = means.get('mean_lwg') or 0.35
    mean_sgr = means.get('mean_sgr') or 2.5
    growth_rate = max(0.05, mean_lwg * (predicted_sgr / max(mean_sgr, 0.1)))
    return growth_rate, 'rrl-sgr-v1'


def _fetch_live_weather_for_growth():
    """Today's Open-Meteo summary for ADG modifiers."""
    try:
        from .ml_feed_recommend import fetch_today_weather
        return fetch_today_weather() or {}
    except Exception as exc:
        logger.debug('Live weather fetch failed: %s', exc)
        return {}


def _latest_pond_sensors():
    """Latest SensorReading for WQ ML (may be None / partial)."""
    try:
        from .models import SensorReading
        return SensorReading.objects.first()
    except Exception:
        return None


def _compute_env_adg_context(latest_metric):
    """
    Build ADG environment modifier from form WQ + live weather + optional WQ ML.
    Returns dict: modifier, notes, wq_class, weather, form_wq, sensor_wq
    """
    notes = []
    mod = 1.0

    form_temp = getattr(latest_metric, 'water_temperature', None)
    form_ph = getattr(latest_metric, 'water_ph', None)
    form_turb = getattr(latest_metric, 'turbidity', None)
    form_tds = getattr(latest_metric, 'tds', None)

    # Form water-quality ranges (shrimp-friendly) — matches SensorReading params
    if form_temp is not None:
        if form_temp < 24 or form_temp > 34:
            mod *= 0.80
            notes.append(f'Water temp {form_temp:.1f}C is outside 24-34C — growth slowed.')
        elif form_temp < 26 or form_temp > 32:
            mod *= 0.90
            notes.append(f'Water temp {form_temp:.1f}C is suboptimal (prefer 26-32C).')
    if form_ph is not None:
        if form_ph < 6.5 or form_ph > 9.0:
            mod *= 0.85
            notes.append(f'pH {form_ph:.2f} is outside 6.5-9 — fix water quality before raising feed.')
        elif form_ph < 7.0 or form_ph > 8.5:
            mod *= 0.93
            notes.append(f'pH {form_ph:.2f} is slightly off optimal 7.0-8.5.')
    if form_turb is not None:
        if form_turb > 100:
            mod *= 0.85
            notes.append(f'Turbidity {form_turb:.1f} NTU is high — slower growth; consider water exchange.')
        elif form_turb > 40:
            mod *= 0.92
            notes.append(f'Turbidity {form_turb:.1f} NTU is elevated.')
    if form_tds is not None and (form_tds < 5 or form_tds > 2000):
        mod *= 0.92
        notes.append(f'TDS {form_tds:.0f} ppm looks unusual — verify probe / salinity.')

    weather = _fetch_live_weather_for_growth()
    air_temp = weather.get('temp_mean')
    precip = weather.get('precip_sum')
    if precip is None:
        precip = weather.get('rain_sum')
    if air_temp is not None:
        if air_temp < 24 or air_temp > 34:
            mod *= 0.88
            notes.append(f'Air temp {air_temp:.1f}C (Open-Meteo) is extreme — reduced ADG.')
        elif air_temp < 26 or air_temp > 32:
            mod *= 0.94
            notes.append(f'Air temp {air_temp:.1f}C is warm/cool — mild ADG reduction.')
    if precip is not None and precip >= 20:
        mod *= 0.88
        notes.append(f'Heavy rain today ({precip:.1f} mm) — expect slower growth / stress.')
    elif precip is not None and precip >= 10:
        mod *= 0.94
        notes.append(f'Moderate rain today ({precip:.1f} mm).')

    # WQ ML from live pond sensors when all 4 valid
    wq_class = None
    sensor = _latest_pond_sensors()
    sensor_vals = {
        'temperature': getattr(sensor, 'temperature', None) if sensor else None,
        'ph': getattr(sensor, 'ph', None) if sensor else None,
        'tds': getattr(sensor, 'tds', None) if sensor else None,
        'turbidity': getattr(sensor, 'turbidity', None) if sensor else None,
    }
    # Prefer form values when sensors missing
    ml_temp = sensor_vals['temperature'] if sensor_vals['temperature'] is not None else form_temp
    ml_ph = sensor_vals['ph'] if sensor_vals['ph'] is not None else form_ph
    ml_tds = sensor_vals['tds'] if sensor_vals['tds'] is not None else form_tds
    ml_turb = sensor_vals['turbidity']
    try:
        from .ml_water_quality import predict_water_quality
        # Only run when we have enough valid inputs (model needs 4)
        if None not in (ml_temp, ml_ph, ml_tds, ml_turb):
            # Reject nonsense pH for ML
            if 1.0 <= float(ml_ph) <= 14.0:
                ml_res = predict_water_quality(
                    temperature=ml_temp, ph=ml_ph, tds=ml_tds, turbidity=ml_turb,
                )
                if ml_res:
                    wq_class = ml_res.get('ml_class')
                    if wq_class == 'Severe':
                        mod *= 0.70
                        notes.append('WQ ML: Severe — strong growth penalty; intervene now.')
                    elif wq_class == 'Warning':
                        mod *= 0.82
                        notes.append('WQ ML: Warning — slower growth until water improves.')
                    elif wq_class == 'Caution':
                        mod *= 0.92
                        notes.append('WQ ML: Caution — monitor closely.')
    except Exception as exc:
        logger.debug('WQ ML for growth skipped: %s', exc)

    mod = float(np.clip(mod, 0.45, 1.15))
    return {
        'modifier': mod,
        'notes': notes,
        'wq_class': wq_class,
        'weather': {
            'temp_mean': air_temp,
            'precip': precip,
        },
        'form_wq': {
            'temperature': form_temp,
            'ph': form_ph,
            'turbidity': form_turb,
            'tds': form_tds,
        },
    }


def _build_action_recommendation_cards(
    *,
    current_weight,
    predicted_weight_adj,
    predicted_count,
    adg_base,
    adg_adjusted,
    env_ctx,
    estimated_harvest,
    model_version,
):
    """
    Structured Feed / Water quality / Growth cards for pond admins.

    Each card: type, title, message (short why), actions (what to do today).
    """
    notes = list(env_ctx.get('notes') or [])
    form_wq = env_ctx.get('form_wq') or {}
    wq_class = env_ctx.get('wq_class')
    mod = float(env_ctx.get('modifier') or 1.0)

    wq_stress = any(
        key in ' '.join(notes).lower()
        for key in ('ph ', 'turbidity', 'wq ml', 'tds ', 'water temp')
    ) or (wq_class in ('Caution', 'Warning', 'Severe'))

    # --- Water quality: parameter-specific actions ---
    wq_actions = []
    temp = form_wq.get('temperature')
    ph = form_wq.get('ph')
    turb = form_wq.get('turbidity')
    tds = form_wq.get('tds')

    if temp is not None:
        if temp < 24:
            wq_actions.append(
                f'Water is cold ({temp:.1f}°C). Reduce feed 30–50% and avoid large water changes.'
            )
        elif temp > 34:
            wq_actions.append(
                f'Water is hot ({temp:.1f}°C). Add shade, increase aeration/exchange, watch for stress.'
            )
        elif temp < 26 or temp > 32:
            wq_actions.append(
                f'Temp {temp:.1f}°C is outside ideal 26–32°C — keep aeration steady and check again tonight.'
            )
        else:
            wq_actions.append(f'Temperature {temp:.1f}°C is in the good range.')

    if ph is not None:
        if ph < 6.5:
            wq_actions.append(
                f'pH is low ({ph:.2f}). Add agricultural lime/dolomite; recheck in 4–6 hours. Do not raise feed.'
            )
        elif ph > 9.0:
            wq_actions.append(
                f'pH is high ({ph:.2f}). Do a 20–30% water exchange; check for heavy algae.'
            )
        elif ph < 7.0 or ph > 8.5:
            wq_actions.append(
                f'pH {ph:.2f} is slightly off (ideal 7.0–8.5). Monitor morning vs afternoon values.'
            )
        else:
            wq_actions.append(f'pH {ph:.2f} is acceptable.')

    if turb is not None:
        if turb > 100:
            wq_actions.append(
                f'Turbidity is high ({turb:.1f} NTU). Partial water change / clarify; cut feed until clearer.'
            )
        elif turb > 40:
            wq_actions.append(
                f'Turbidity elevated ({turb:.1f} NTU). Check leftover feed and algae; prepare a small exchange.'
            )
        else:
            wq_actions.append(f'Turbidity {turb:.1f} NTU looks fine.')

    if tds is not None:
        if tds < 5 or tds > 2000:
            wq_actions.append(
                f'TDS {tds:.0f} ppm looks unusual — verify the probe, then check salinity/minerals.'
            )
        else:
            wq_actions.append(f'TDS {tds:.0f} ppm is within a usable range.')

    weather = env_ctx.get('weather') or {}
    precip = weather.get('precip')
    if precip is not None and precip >= 20:
        wq_actions.append(
            f'Heavy rain expected/recorded ({precip:.1f} mm). Watch for pH/temp swings; do not overfeed.'
        )
    elif precip is not None and precip >= 10:
        wq_actions.append(f'Moderate rain ({precip:.1f} mm) — recheck water after the rain stops.')

    if wq_class in ('Warning', 'Severe'):
        wq_actions.insert(
            0,
            f'ML water-quality class is {wq_class}. Treat this as priority #1 before changing feed.'
        )
    elif wq_class == 'Caution':
        wq_actions.insert(0, 'ML water-quality class is Caution — monitor every few hours today.')

    if not wq_actions:
        wq_actions = [
            'No saved water readings yet. On the left: Fill from DB → Save, then click Regenerate ML forecast.',
        ]

    if wq_stress:
        wq_title = 'Fix water quality first'
        wq_msg = 'Pond conditions may slow growth. Correct water before increasing feed.'
        wq_type = 'critical' if wq_class in ('Warning', 'Severe') else 'warning'
    else:
        wq_title = 'Water looks manageable'
        wq_msg = 'Temp, pH, TDS, and turbidity support normal operations today.'
        wq_type = 'info'

    # --- Growth ---
    harvest_str = (
        estimated_harvest.isoformat()
        if hasattr(estimated_harvest, 'isoformat')
        else str(estimated_harvest)
    )
    grams_per_day = max(0.0, float(adg_adjusted))
    growth_actions = [
        f'Expected weight gain ≈ {grams_per_day:.2f} g/shrimp/day '
        f'(model {model_version}; environment factor {mod:.0%}).',
        f'Current average weight {current_weight:.2f} g → near-term forecast {predicted_weight_adj:.2f} g.',
        f'Estimated harvest window around {harvest_str} (target ~18 g).',
    ]
    if adg_adjusted < 0.15:
        growth_title = 'Growth looks slow'
        growth_msg = 'Daily gain is below a healthy pace. Check feed leftover and water first.'
        growth_type = 'warning'
        growth_actions.append('Walk the pond: uneaten feed, soft shells, unusual swimming.')
        growth_actions.append('After water is stable, slightly increase feed using the ML feed amount below.')
    elif adg_adjusted < adg_base * 0.92:
        growth_title = 'Weather/water is slowing growth'
        growth_msg = (
            f'Baseline gain was {adg_base:.2f} g/day; adjusted to {adg_adjusted:.2f} g/day '
            'because of water or weather stress.'
        )
        growth_type = 'warning'
        growth_actions.append('Do not chase growth with heavy feed until water notes above are clear.')
    else:
        growth_title = 'Growth on track'
        growth_msg = 'Weight gain looks consistent with stocking, feed, and conditions.'
        growth_type = 'info'
        growth_actions.append('Keep the same sampling routine (count + average weight) every few days.')

    if predicted_weight_adj >= 18:
        growth_actions.append('Shrimp are near harvest size — plan harvest logistics this week.')
    elif predicted_weight_adj >= 15:
        growth_actions.append('Approaching harvest weight — sample more often and watch market size.')
    if predicted_count is not None and predicted_count < 100:
        growth_actions.append('Predicted stock looks very low — verify mortality records and recent counts.')

    # --- Feed ---
    feed_actions = [
        'Use the green ML feed box below for today’s total kg and the 5 feeding times.',
        'Open Feeding → “Use as today’s feed” to push that plan to the auto-feeder.',
    ]
    if wq_stress:
        feed_title = 'Hold feed increases'
        feed_msg = 'Water/weather stress detected — keep feed steady or slightly lower until water improves.'
        feed_type = 'warning'
        feed_actions.insert(0, 'Do not increase ration today. Prefer the ML amount or a little less.')
        feed_actions.append('Check trays/pond bottom 1–2 hours after feeding for leftovers.')
    elif adg_adjusted < 0.15:
        feed_title = 'Review feed amount'
        feed_msg = 'Growth is soft. After water is OK, follow ML feed (or +5–10% if trays are clean).'
        feed_type = 'warning'
        feed_actions.insert(0, 'Confirm trays are empty before any increase.')
    else:
        feed_title = 'Follow today’s ML feed plan'
        feed_msg = 'Feed from shrimp count, average weight, culture day, and weather.'
        feed_type = 'info'
        feed_actions.insert(0, 'Apply the ML kg total and time slots; do not guess a random amount.')

    def _card(title, message, actions, ctype):
        return {
            'type': ctype,
            'title': _strip_non_bmp(title),
            'message': _strip_non_bmp(message),
            'actions': [_strip_non_bmp(a) for a in actions],
        }

    return {
        'feed': _card(feed_title, feed_msg, feed_actions, feed_type),
        'water_quality': _card(wq_title, wq_msg, wq_actions, wq_type),
        'growth': _card(growth_title, growth_msg, growth_actions, growth_type),
    }


def generate_growth_predictions(season, days_ahead=30):
    """
    Generate growth predictions for a season.

    Prefers sampling-trained ADG model (growthRateDataset batches),
    then applies environment modifiers (form WQ + live weather + WQ ML).
    Stores adjusted ABW in predicted_avg_weight_grams; base ABW + cards in recommendation JSON.
    """
    import json
    from .models import GrowthPrediction

    latest_metric = season.growth_metrics.order_by('-date').first()
    if not latest_metric:
        logger.warning(f'No growth metrics found for season {season.id}')
        return []

    predictor = ShrimpGrowthPredictor()
    predictions = []

    current_weight = latest_metric.avg_weight_grams or 0
    current_count = latest_metric.shrimp_count or 1
    current_date = latest_metric.date

    growth_rate = 0.15
    model_version = 'fallback-linear-1.0'
    current_doc = None

    if predictor.model is not None:
        try:
            if predictor.model_family == 'sampling_growth_v1' or (
                predictor.feature_names and 'doc' in (predictor.feature_names or [])
            ):
                growth_rate, current_doc, model_version, _feats = _predict_adg_sampling(
                    predictor, season, latest_metric
                )
            else:
                growth_rate, model_version = _predict_adg_rrl(predictor, latest_metric)
        except Exception as e:
            logger.warning(f'Growth model predict failed, using fallback: {e}')
            growth_rate = float(predictor.mean_adg or 0.15)
            model_version = 'fallback-linear-1.0'

    # Observed ADG from latest metric overrides if model missing and metric present
    if model_version.startswith('fallback') and latest_metric.daily_weight_gain_grams:
        try:
            observed = float(latest_metric.daily_weight_gain_grams)
            if 0.05 <= observed <= 1.2:
                growth_rate = observed
                model_version = 'observed-adg-1.0'
        except (TypeError, ValueError):
            pass

    adg_base = float(growth_rate)
    env_ctx = _compute_env_adg_context(latest_metric)
    adg_modifier = float(env_ctx['modifier'])
    adg_adjusted = float(np.clip(adg_base * adg_modifier, 0.03, 1.2))
    model_version_adj = f'{model_version}+env'

    initial_count = (
        getattr(season, 'initial_shrimp_quantity', 0)
        or season.stocking_density
        or current_count
    )

    # Harvest date from environment-adjusted ADG
    target_weight = 18.0
    if adg_adjusted > 0 and current_weight < target_weight:
        days_to_harvest = int(np.ceil((target_weight - current_weight) / adg_adjusted))
        estimated_harvest = current_date + timedelta(days=days_to_harvest)
    else:
        estimated_harvest = predictor.predict_harvest_date(
            current_date, current_weight, target_weight=target_weight
        )

    cards = _build_action_recommendation_cards(
        current_weight=current_weight,
        predicted_weight_adj=current_weight + adg_adjusted,
        predicted_count=current_count,
        adg_base=adg_base,
        adg_adjusted=adg_adjusted,
        env_ctx=env_ctx,
        estimated_harvest=estimated_harvest,
        model_version=model_version,
    )

    for day_offset in range(1, days_ahead + 1):
        forecast_date = current_date + timedelta(days=day_offset)
        base_weight = current_weight + (adg_base * day_offset)
        adjusted_weight = current_weight + (adg_adjusted * day_offset)

        # Optional: blend adjusted path with ABW-vs-DOC curve if available
        if (
            predictor.abw_curve_model is not None
            and current_doc is not None
            and predictor.abw_curve_features
        ):
            try:
                curve_now = float(
                    predictor.abw_curve_model.predict(
                        np.array([[float(current_doc), float(initial_count)]])
                    )[0]
                )
                curve_fut = float(
                    predictor.abw_curve_model.predict(
                        np.array([[float(current_doc + day_offset), float(initial_count)]])
                    )[0]
                )
                blended = current_weight + (curve_fut - curve_now)
                # Apply same env stress to the blend
                base_weight = 0.65 * base_weight + 0.35 * blended
                adjusted_weight = 0.65 * adjusted_weight + 0.35 * (current_weight + (curve_fut - curve_now) * adg_modifier)
            except Exception:
                pass

        base_weight = max(0.1, float(base_weight))
        adjusted_weight = max(0.1, float(adjusted_weight))
        predicted_count = int(current_count * (1 - (0.002 * day_offset / 7)))
        predicted_count = max(1, predicted_count)
        survival_rate = (predicted_count / initial_count * 100) if initial_count > 0 else 100
        confidence = max(50, 95 - (day_offset * 2))

        # Refresh growth card harvest wording using this day's adjusted weight
        day_cards = dict(cards)
        if day_offset == 1:
            day_cards = _build_action_recommendation_cards(
                current_weight=current_weight,
                predicted_weight_adj=adjusted_weight,
                predicted_count=predicted_count,
                adg_base=adg_base,
                adg_adjusted=adg_adjusted,
                env_ctx=env_ctx,
                estimated_harvest=estimated_harvest,
                model_version=model_version,
            )

        day_payload_cards = day_cards if day_offset == 1 else cards
        payload = {
            'schema': 'growth_rec_v3',
            'base_abw': round(base_weight, 2),
            'adjusted_abw': round(adjusted_weight, 2),
            'adg_base': round(adg_base, 4),
            'adg_adjusted': round(adg_adjusted, 4),
            'adg_modifier': round(adg_modifier, 3),
            'wq_class': env_ctx.get('wq_class'),
            'env_notes': env_ctx.get('notes') or [],
            'weather': env_ctx.get('weather') or {},
            'form_wq': env_ctx.get('form_wq') or {},
            'cards': day_payload_cards,
            'summary': _strip_non_bmp(
                f"{day_payload_cards['growth'].get('title', 'Growth')}: "
                f"{day_payload_cards['growth'].get('message', '')} "
                f"Expected ~{adg_adjusted:.2f} g/day."
            ),
        }

        prediction = GrowthPrediction(
            season=season,
            prediction_date=current_date,
            forecast_date=forecast_date,
            predicted_avg_weight_grams=round(adjusted_weight, 2),
            predicted_shrimp_count=predicted_count,
            predicted_survival_rate_percent=round(survival_rate, 1),
            estimated_harvest_date=estimated_harvest,
            confidence_score=confidence,
            recommendation=_strip_non_bmp(json.dumps(payload, ensure_ascii=True)),
            model_version=model_version_adj,
            is_active=True,
        )
        predictions.append(prediction)

    return predictions


def _strip_non_bmp(text):
    """Strip non-BMP characters (e.g., many emojis) for MySQL utf8 (3-byte) safety."""
    if not text:
        return text
    return ''.join(ch for ch in str(text) if ord(ch) <= 0xFFFF)


def _generate_recommendation(predicted_weight, current_weight, predicted_count):
    """Legacy plain-text recommendation (kept for callers)."""
    recommendations = []
    growth_potential = predicted_weight - current_weight
    if growth_potential < 0.5:
        recommendations.append('Growth rate is below optimal. Consider increasing feed.')
    elif growth_potential > 2:
        recommendations.append('Excellent growth trajectory! Maintain current feeding.')
    if predicted_count < 100:
        recommendations.append('Low survival rate detected. Check water quality.')
    if predicted_weight >= 18:
        recommendations.append('Estimated ready for harvest in 7-10 days')
    elif predicted_weight >= 15:
        recommendations.append('Approaching harvest weight. Monitor daily.')
    if not recommendations:
        recommendations.append('Continue current feeding and monitoring schedule.')
    return ' | '.join(recommendations)


def parse_growth_recommendation(raw):
    """Parse recommendation JSON payload; return dict or None."""
    import json
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get('schema') in ('growth_rec_v2', 'growth_rec_v3'):
            return data
    except Exception:
        return None
    return None


def analyze_season_performance(season):
    """
    Analyze season performance and generate summary statistics.
    
    Returns dict with analytics.
    """
    from .models import DailyGrowthMetric
    from django.db.models import Avg, Max, Min, Sum
    
    metrics = season.growth_metrics.all()
    if not metrics.exists():
        return None
    
    agg = metrics.aggregate(
        avg_weight=Avg('avg_weight_grams'),
        max_weight=Max('avg_weight_grams'),
        min_weight=Min('avg_weight_grams'),
        avg_mortality=Avg('daily_mortality_percent'),
        total_feed=Sum('feed_amount_grams'),
        avg_temp=Avg('water_temperature'),
        avg_ph=Avg('water_ph'),
    )
    
    first_metric = metrics.order_by('date').first()
    last_metric = metrics.order_by('-date').first()
    
    return {
        'days_tracked': (last_metric.date - first_metric.date).days,
        'initial_weight': first_metric.avg_weight_grams,
        'final_weight': last_metric.avg_weight_grams,
        'total_weight_gain': last_metric.avg_weight_grams - first_metric.avg_weight_grams,
        'average_daily_gain': (last_metric.avg_weight_grams - first_metric.avg_weight_grams) / max(1, (last_metric.date - first_metric.date).days),
        'initial_count': first_metric.shrimp_count,
        'final_count': last_metric.shrimp_count,
        'survival_rate': (last_metric.shrimp_count / first_metric.shrimp_count * 100) if first_metric.shrimp_count > 0 else 0,
        **agg,
    }
