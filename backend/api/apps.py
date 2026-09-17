from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        """Register signals and load ML models (dev only)."""
        # Always register signals (do not gate on RUN_MAIN).
        try:
            from . import signals  # noqa: F401
        except Exception as e:
            # Keep app startup resilient; signals are optional for some deployments.
            print(f"[API] Failed to import signals: {e}")

        # Load ML models synchronously for debugging (avoid double-loading under autoreload).
        import os

        if os.environ.get('RUN_MAIN') != 'true':
            return

        skip_all = os.environ.get('SKIP_HEAVY_ML', '').lower() in ('1', 'true', 'yes')
        skip_weather = os.environ.get('SKIP_WEATHER_ML', '').lower() in ('1', 'true', 'yes')

        if skip_all:
            print('[INFO] SKIP_HEAVY_ML set — skipping all ML startup loads (API runs without predictors).')
            return

        print("Loading predictors synchronously...")
        from .ml_loader import load_weather_predictor
        if not skip_weather:
            load_weather_predictor()
        else:
            print('[INFO] SKIP_WEATHER_ML set — skipping EnhancedWeatherPredictor.')

        print("ML models loaded successfully")
