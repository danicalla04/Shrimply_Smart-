import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '\\..')

from api.weather_predictor import weather_predictor as wp


def test_models_and_scalers_loaded():
    # models and scalers should be dictionaries and contain key artifacts
    assert isinstance(wp.models, dict)
    assert 'temperature_model' in wp.models
    assert isinstance(wp.scalers, dict)


def test_predict_tomorrow_structure():
    out = wp.predict_tomorrow(city='Calapan', save_to_db=False)
    assert isinstance(out, dict)
    # basic keys
    for k in ('date', 'city', 'temperature', 'humidity', 'precipMm'):
        assert k in out
