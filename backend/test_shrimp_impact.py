#!/usr/bin/env python3
"""
Test script for shrimp farming weather impact analysis
"""
import sys
import os
import json
from datetime import datetime

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Mock Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')

import django
django.setup()

from api.enhanced_weather_predictor import EnhancedWeatherPredictor

def test_shrimp_impact_analysis():
    """Test the shrimp farming weather impact analysis"""

    # Initialize predictor
    predictor = EnhancedWeatherPredictor()

    # Test cases with different weather conditions
    test_cases = [
        {
            'name': 'Optimal Conditions',
            'weather': {
                'temperature': 28,
                'humidity': 75,
                'windKmh': 15,
                'precipMm': 0,
                'pressure': 1013,
                'description': 'clear sky',
                'city': 'Calapan'
            }
        },
        {
            'name': 'Extreme Heat',
            'weather': {
                'temperature': 36,
                'humidity': 60,
                'windKmh': 10,
                'precipMm': 0,
                'pressure': 1010,
                'description': 'sunny',
                'city': 'Calapan'
            }
        },
        {
            'name': 'Heavy Rain',
            'weather': {
                'temperature': 26,
                'humidity': 90,
                'windKmh': 20,
                'precipMm': 60,
                'pressure': 1000,
                'description': 'heavy rain',
                'city': 'Calapan'
            }
        },
        {
            'name': 'Cold Weather',
            'weather': {
                'temperature': 18,
                'humidity': 85,
                'windKmh': 5,
                'precipMm': 2,
                'pressure': 1020,
                'description': 'cloudy',
                'city': 'Calapan'
            }
        }
    ]

    print("🦐 Testing Shrimp Farming Weather Impact Analysis")
    print("=" * 60)

    for test_case in test_cases:
        print(f"\n📊 Test Case: {test_case['name']}")
        print("-" * 40)

        try:
            result = predictor.get_weather_impact_for_shrimp(test_case['weather'])

            print(f"Overall Status: {result['overall_status'].upper()}")
            print(f"Message: {result['overall_message']}")

            print(f"\nParameter Assessments:")
            for param, assessment in result['assessments'].items():
                status_icon = {'good': '✅', 'moderate': '⚠️', 'poor': '❌'}[assessment['status']]
                print(f"  {status_icon} {param.title()}: {assessment['message']}")

            print(f"\nRisk Summary: High: {result['risk_summary']['high']}, Medium: {result['risk_summary']['medium']}, Low: {result['risk_summary']['low']}")

            if result['recommendations']:
                print(f"\n💡 Key Recommendations:")
                for rec in result['recommendations'][:3]:  # Show first 3
                    print(f"  • {rec}")

            print(f"\n📍 Location: {result['location']}")

        except Exception as e:
            print(f"❌ ERROR: {e}")

    print("\n" + "=" * 60)
    print("✅ Shrimp Impact Analysis Test Complete")

if __name__ == '__main__':
    test_shrimp_impact_analysis()