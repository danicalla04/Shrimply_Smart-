import json
from pathlib import Path
md = Path(r'c:\wamp64\www\Shrimply_Smart\dataset\models')
print('=' * 60)
print('  ML MODEL ACCURACY SUMMARY')
print('=' * 60)
print()
print('  WEATHER PREDICTION MODELS (XGBoost)')
print('-' * 60)
weather_metrics_path = md / 'weather_model_metrics.json'
if weather_metrics_path.exists():
    wm = json.load(open(weather_metrics_path))
    for k, v in wm.items():
        pct = v['r2'] * 100
        print(f"  {k:15s}  R² = {v['r2']:.4f}  ({pct:.1f}%)")
else:
    print(f"  (missing: {weather_metrics_path})")
print('=' * 60)
