#!/usr/bin/env python
"""
Quick-start setup script for ShrimplySmart backend
Configures database, creates admin user, loads initial data
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

django.setup()

from django.contrib.auth import get_user_model
from api.models import Threshold, Feeder
from datetime import datetime

User = get_user_model()

def setup_database():
    """Run migrations"""
    print("📦 Running database migrations...")
    os.system('python manage.py migrate')
    print("✅ Migrations complete\n")

def create_admin_user():
    """Create superuser if doesn't exist"""
    if User.objects.filter(username='admin').exists():
        print("✅ Admin user already exists")
        return
    
    print("👤 Creating admin user...")
    User.objects.create_superuser(
        username='admin',
        email='admin@shrimplysmart.local',
        password='admin123'  # CHANGE THIS IN PRODUCTION!
    )
    print("✅ Admin user created (username: admin, password: admin123)\n")

def load_thresholds():
    """Load default water quality thresholds"""
    print("⚙️  Loading water quality thresholds...")
    
    thresholds = [
        {
            'parameter': 'temperature',
            'min_value': 24.0,
            'max_value': 32.0,
            'unit': '°C',
            'description': 'Optimal range for shrimp growth'
        },
        {
            'parameter': 'ph',
            'min_value': 7.5,
            'max_value': 8.5,
            'unit': 'pH',
            'description': 'Stable alkaline environment'
        },
        {
            'parameter': 'turbidity',
            'min_value': 0.5,
            'max_value': 3.0,
            'unit': 'NTU',
            'description': 'Water turbidity level'
        },
        {
            'parameter': 'tds',
            'min_value': 10,
            'max_value': 30,
            'unit': 'ppt',
            'description': 'Total Dissolved Solids (salinity)'
        },
    ]
    
    for threshold_data in thresholds:
        param = threshold_data['parameter']
        if Threshold.objects.filter(parameter=param).exists():
            print(f"  ℹ️  {param} threshold already exists, skipping")
            continue
        
        Threshold.objects.create(**threshold_data)
        print(f"  ✅ Created {param} threshold: {threshold_data['min_value']}-{threshold_data['max_value']} {threshold_data['unit']}")
    
    print("✅ Thresholds loaded\n")

def initialize_feeder():
    """Initialize feeder system"""
    print("🍗 Initializing feeder system...")
    
    if Feeder.objects.exists():
        print("✅ Feeder already initialized")
        return
    
    feeder = Feeder.objects.create(
        capacity_max=5000,  # 5kg
        capacity_current=5000,
        portion_grams=50,
        interval_minutes=120,  # Feed every 2 hours
        schedule_type='interval',
        auto_enabled=False,
        weather_adaptation=True,
        smart_optimization=True,
    )
    print(f"✅ Feeder created: {feeder.capacity_max}g capacity, {feeder.portion_grams}g portions\n")

def verify_ml_models():
    """Check if ML models exist"""
    print("🤖 Checking ML models...")
    from pathlib import Path
    
    models_dir = Path(__file__).parent.parent / 'dataset' / 'models'
    
    required_models = [
        'temperature_model.pkl',
        'humidity_model.pkl',
        'rainfall_model.pkl',
        'wind_speed_model.pkl',
        'pressure_model.pkl',
    ]
    
    existing = [f for f in required_models if (models_dir / f).exists()]
    missing = [f for f in required_models if f not in existing]
    
    print(f"  ✅ Found {len(existing)}/{len(required_models)} core models")
    
    if missing:
        print(f"  ⚠️  Missing models: {', '.join(missing)}")
        print("  💡 Run: python dataset/train_optuna.py to train missing models")
    
    print()

def verify_firebase_config():
    """Check Firebase configuration"""
    print("🔥 Checking Firebase configuration...")
    
    firebase_path = os.getenv('FIREBASE_CREDENTIAL_PATH')
    firebase_url = os.getenv('FIREBASE_DB_URL')
    
    if not firebase_path:
        print("  ⚠️  FIREBASE_CREDENTIAL_PATH not set in .env")
        return False
    
    if not firebase_url:
        print("  ⚠️  FIREBASE_DB_URL not set in .env")
        return False
    
    if not os.path.exists(firebase_path):
        print(f"  ❌ Firebase credentials file not found: {firebase_path}")
        return False
    
    print(f"  ✅ FIREBASE_CREDENTIAL_PATH: {firebase_path}")
    print(f"  ✅ FIREBASE_DB_URL: {firebase_url}")
    return True

def main():
    print("\n" + "="*60)
    print("🦐 ShrimplySmart Backend Setup")
    print("="*60 + "\n")
    
    try:
        setup_database()
        create_admin_user()
        load_thresholds()
        initialize_feeder()
        verify_ml_models()
        firebase_ok = verify_firebase_config()
        
        print("="*60)
        print("✅ Setup Complete!")
        print("="*60)
        print("\n📝 Next Steps:")
        print("  1. Start Django server: python manage.py runserver 0.0.0.0:8000")
        print("  2. Access admin panel: http://localhost:8000/admin/")
        print("  3. Login with: admin / admin123")
        
        if not firebase_ok:
            print("\n⚠️  Firebase configuration incomplete - some features won't work")
        
        print("\n🚀 Then start the Arduino and frontend to see real-time updates!\n")
        
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
