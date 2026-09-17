"""Centralised, lazy-loaded predictor registry.

This module currently manages the singleton weather predictor.
"""

import logging
import threading

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# ── Weather predictor ─────────────────────────────────────────────────
_weather_predictor = None
_weather_loaded = False


def load_weather_predictor():
    """Instantiate the EnhancedWeatherPredictor (called once from AppConfig)."""
    global _weather_predictor, _weather_loaded

    if _weather_loaded:
        return

    try:
        from .enhanced_weather_predictor import EnhancedWeatherPredictor
        with _lock:
            _weather_predictor = EnhancedWeatherPredictor()
        logger.info("[OK] EnhancedWeatherPredictor loaded")
        print("[OK] EnhancedWeatherPredictor loaded")
    except Exception as e:
        print(f"[WARN] Failed to load EnhancedWeatherPredictor: {e}")
    finally:
        _weather_loaded = True


def get_weather_predictor():
    """Return the singleton EnhancedWeatherPredictor (or None if not yet loaded)."""
    return _weather_predictor
