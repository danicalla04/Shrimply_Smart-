"""Import real sensor data from CSV files.

Converts dissolved_oxygen readings to turbidity values and loads into database.
Usage:
  python import_live_sensor_data.py <csv_file>
  python import_live_sensor_data.py ../input/small-aquaculture-fishpond/pond_iot_2023.csv
"""
import os
import sys
import csv
import django
from datetime import datetime
from pathlib import Path

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
django.setup()

from api.models import SensorReading
from django.utils import timezone
from django.db import transaction


def convert_do_to_turbidity(do_value):
    """
    Convert DO (Dissolved Oxygen) readings to turbidity values.
    
    DO range: ~4-10 mg/L (higher = better oxygen)
    Turbidity range: 0.5-4 NTU (lower = clearer water)
    
    Inverse relationship: High DO (well aerated) = Low turbidity (clear)
    Low DO (stagnant) = High turbidity (cloudy)
    
    Mapping:
      DO 10 -> Turbidity 0.5 (excellent oxygen, very clear)
      DO 7 -> Turbidity 1.5 (good oxygen, reasonably clear)
      DO 5 -> Turbidity 2.5 (acceptable, cloudier)
      DO 4 -> Turbidity 3.5 (poor, very cloudy)
    """
    # Linear interpolation: turbidity = 4.5 - (0.4 * do_value)
    turbidity = 4.5 - (0.4 * float(do_value))
    # Clamp to reasonable range
    turbidity = max(0.5, min(4.0, turbidity))
    return round(turbidity, 2)


def import_csv(csv_file):
    """Import sensor readings from CSV file."""
    
    if not os.path.exists(csv_file):
        print(f"ERROR: File not found: {csv_file}")
        return False
    
    print(f"Importing live sensor data from: {csv_file}\n")
    
    readings_to_create = []
    skipped = 0
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row_idx, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            try:
                # Parse CSV columns
                reading_id = int(row['id'])
                created_date_str = row['created_date']
                ph = float(row['water_pH'])
                tds = int(float(row['TDS']))
                temperature = float(row['water_temp'])
                do_value = float(row['dissolved_oxygen'])
                
                # Convert DO to turbidity
                turbidity = convert_do_to_turbidity(do_value)
                
                # Parse timestamp - handle format: "1/26/2023 11:24"
                try:
                    ts = datetime.strptime(created_date_str, '%m/%d/%Y %H:%M')
                except ValueError:
                    try:
                        ts = datetime.strptime(created_date_str, '%m/%d/%Y %H:%M:%S')
                    except ValueError:
                        print(f"  Row {row_idx}: ERROR parsing date '{created_date_str}'")
                        skipped += 1
                        continue
                
                # Convert to timezone-aware datetime
                ts_aware = timezone.make_aware(ts, timezone=timezone.utc)
                
                # Create SensorReading object
                reading = SensorReading(
                    temperature=temperature,
                    ph=ph,
                    turbidity=turbidity,
                    tds=tds,
                    timestamp=ts_aware
                )
                readings_to_create.append(reading)
                
                if row_idx % 100 == 0:
                    print(f"  Processed {row_idx} rows...")
                    
            except (ValueError, KeyError) as e:
                print(f"  Row {row_idx}: ERROR - {e}")
                print(f"    Data: {row}")
                skipped += 1
                continue
    
    if not readings_to_create:
        print("ERROR: No valid readings to import")
        return False
    
    # Batch create readings
    print(f"\nCreating {len(readings_to_create)} sensor readings in database...")
    try:
        with transaction.atomic():
            SensorReading.objects.bulk_create(readings_to_create, batch_size=500)
        print(f"✓ Successfully imported {len(readings_to_create)} readings")
    except Exception as e:
        print(f"ERROR during bulk create: {e}")
        return False
    
    if skipped > 0:
        print(f"⚠ Skipped {skipped} invalid rows")
    
    # Print summary
    print(f"\n=== Import Summary ===")
    first = readings_to_create[0]
    last = readings_to_create[-1]
    print(f"Date range: {first.timestamp} to {last.timestamp}")
    print(f"Total readings in DB: {SensorReading.objects.count()}")
    
    # Print sample readings
    print(f"\nSample readings (DO → Turbidity conversion):")
    samples = [readings_to_create[0], readings_to_create[len(readings_to_create)//4], 
               readings_to_create[len(readings_to_create)//2], readings_to_create[-1]]
    for r in samples:
        print(f"  {r.timestamp.strftime('%m/%d %H:%M')} | T={r.temperature}°C  pH={r.ph}  TURB={r.turbidity}NTU  TDS={r.tds}ppm")
    
    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python import_live_sensor_data.py <csv_file>")
        print("\nExample:")
        print("  python import_live_sensor_data.py ../input/small-aquaculture-fishpond/pond_iot_2023.csv")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    success = import_csv(csv_file)
    sys.exit(0 if success else 1)
