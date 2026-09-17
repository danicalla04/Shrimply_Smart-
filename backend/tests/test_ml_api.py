import requests, json

# Test Weather endpoint
print("=" * 60)
print("  Testing Weather ML Ensemble Endpoint")
print("=" * 60)
r = requests.get('http://localhost:8000/api/weather/complete/', params={'location': 'Oriental Mindoro'})
print(f"Status: {r.status_code}")
d = r.json()
if 'weekly_forecast' in d:
    print(f"{'Date':12s} {'Day':10s} {'Temp':>6s} {'Hum':>5s} {'Rain':>6s} {'Wind':>6s} {'Press':>7s} Source")
    print("-" * 70)
    for day in d['weekly_forecast']:
        print(f"{day.get('date',''):12s} {day.get('day',''):10s} {day.get('temperature',''):6.1f} {day.get('humidity',''):5d} {day.get('precipMm',0):6.2f} {day.get('windKmh',0):6.1f} {day.get('pressure',0):7.1f} {day.get('source','api')[:20]}")
elif 'error' in d:
    print(f"Error: {d['error']}")
print()

# Test weather model metrics
print("=" * 60)
print("  Model Accuracy Summary")
print("=" * 60)
import json as j
from pathlib import Path
md = Path(r'c:\wamp64\www\Shrimply_Smart\dataset\models')
wm = md / 'weather_model_metrics.json'
if wm.exists():
    with open(wm) as f:
        met = j.load(f)
    for k, v in met.items():
        print(f"  Weather {k:15s}: R² = {v['r2']:.4f}  RMSE = {v['rmse']:.4f}")
