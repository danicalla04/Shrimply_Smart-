import sys
sys.path.insert(0, r'C:\wamp64\www\Shrimply_Smart\backend')
try:
    from api import weather_predictor
    print('Imported weather_predictor, loaded model keys:')
    print(list(weather_predictor.models.keys()))
except Exception as e:
    print('Import failed:', e)
