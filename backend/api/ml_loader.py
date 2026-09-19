"""Centralised, lazy-loaded predictor registry.

This module currently manages the singleton weather predictor.
"""

import builtins
import logging
import sys
import threading

logger = logging.getLogger(__name__)

_orig_print = builtins.print


def _safe_print(*args, **kwargs):
    try:
        _orig_print(*args, **kwargs)
    except UnicodeEncodeError:
        text = ' '.join(str(a) for a in args)
        _orig_print(text.encode('ascii', 'replace').decode('ascii'), **kwargs)


builtins.print = _safe_print

_lock = threading.Lock()

# ── Weather predictor ─────────────────────────────────────────────────
_weather_predictor = None
_weather_loaded = False


def _safe_stdio():
    """Windows cp1252 consoles crash on emoji/mojibake prints during import."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


def load_weather_predictor():
    """Instantiate the EnhancedWeatherPredictor (called once from AppConfig)."""
    global _weather_predictor, _weather_loaded

    if _weather_loaded:
        return

    _safe_stdio()
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
