import sys
sys.path.insert(0, r'C:\wamp64\www\Shrimply_Smart\backend')

try:
    from api.weather_predictor import weather_predictor as wp
    print('Loaded model keys:')
    print(list(wp.models.keys()))
    print('\nCalling predict_tomorrow() for sample location...')
    out = wp.predict_tomorrow(city='Calapan', save_to_db=False)
    print('\nPredict_tomorrow output:')
    print(out)
except Exception as e:
    print('Error during inference test:', e)
