"""Initialize database with required seed data."""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
django.setup()

from django.contrib.auth.models import User
from api.models import Threshold, Feeder, SensorReading


def main():
    print("=== ShrimplySmart Database Initialization ===\n")

    # 1. Create admin user
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@shrimplysmart.local', 'admin123')
        print("[OK] Created admin user (admin / admin123)")
    else:
        print("[OK] Admin user already exists")

    # 2. Create default thresholds for shrimp farming
    thresholds = {
        'temperature': {'min': 24, 'max': 32, 'unit': 'C'},
        'ph':          {'min': 6.5, 'max': 8.5, 'unit': ''},
        'turbidity':   {'min': 0.5, 'max': 3.0, 'unit': 'NTU'},
        'tds':         {'min': 100, 'max': 500, 'unit': 'ppm'},
    }
    for param, vals in thresholds.items():
        obj, created = Threshold.objects.update_or_create(
            parameter=param,
            defaults={
                'min_value': vals['min'],
                'max_value': vals['max'],
                'unit': vals['unit'],
            }
        )
        status = "CREATED" if created else "EXISTS"
        print(f"[OK] Threshold {param}: {vals['min']}-{vals['max']} {vals['unit']} ({status})")

    # 3. Create feeder
    if not Feeder.objects.exists():
        Feeder.objects.create(
            capacity_max=1000,
            capacity_current=1000,
            portion_grams=50,
            interval_minutes=60,
            auto_enabled=False,
            smart_optimization=True,
            weather_adaptation=True,
            alerts_enabled=True,
        )
        print("[OK] Created default feeder (1000g capacity)")
    else:
        feeder = Feeder.objects.first()
        print(f"[OK] Feeder exists: {feeder.capacity_current}/{feeder.capacity_max}g")

    # 4. Create sample sensor reading if none exist
    if not SensorReading.objects.exists():
        SensorReading.objects.create(
            temperature=27.5,
            ph=7.8,
            turbidity=1.5,
            tds=350
        )
        print("[OK] Created sample sensor reading (27.5C, pH 7.8, Turbidity 1.5NTU, TDS 350)")
    else:
        count = SensorReading.objects.count()
        latest = SensorReading.objects.first()
        print(f"[OK] {count} sensor readings exist (latest: {latest.temperature}C)")

    print("\n=== Database initialization complete! ===")
    print(f"    Admin panel: http://localhost:8000/admin/")
    print(f"    API root:    http://localhost:8000/api/")
    print(f"    Login:       admin / admin123")


if __name__ == '__main__':
    main()
