from django.core.management.base import BaseCommand
from api.models import WeatherForecast
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Load weather data from CSV into WeatherForecast model'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            help='Path to the weather CSV file'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of records to process in each batch'
        )
        parser.add_argument(
            '--forecast-date',
            type=str,
            default=None,
            help='Forecast date (YYYY-MM-DD), defaults to today'
        )
        parser.add_argument(
            '--forecast-type',
            type=str,
            default='current',
            choices=['current', 'tomorrow', 'daily'],
            help='Type of forecast'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing data before loading'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        batch_size = options['batch_size']
        forecast_type = options['forecast_type']
        clear_existing = options['clear_existing']

        # Parse forecast date
        if options['forecast_date']:
            forecast_date = datetime.strptime(options['forecast_date'], '%Y-%m-%d').date()
        else:
            forecast_date = datetime.now().date()

        self.stdout.write(f"Loading weather data from {csv_file}")
        self.stdout.write(f"Forecast date: {forecast_date}, Type: {forecast_type}")

        # Clear existing data if requested
        if clear_existing:
            deleted = WeatherForecast.objects.filter(
                forecast_date=forecast_date,
                forecast_type=forecast_type
            ).delete()[0]
            self.stdout.write(f"Cleared {deleted} existing records")

        # Read CSV
        try:
            df = pd.read_csv(csv_file)
            total_rows = len(df)
            self.stdout.write(f"Found {total_rows} rows in CSV")
        except Exception as e:
            self.stderr.write(f"Error reading CSV: {e}")
            return

        # Process in batches
        created = 0
        updated = 0
        errors = 0

        for start_idx in range(0, total_rows, batch_size):
            end_idx = min(start_idx + batch_size, total_rows)
            batch_df = df.iloc[start_idx:end_idx]

            self.stdout.write(f"Processing batch {start_idx//batch_size + 1}: rows {start_idx+1}-{end_idx}")

            for _, row in batch_df.iterrows():
                try:
                    # Map CSV columns to model fields
                    weather_data = self.map_csv_to_model(row, forecast_date, forecast_type)

                    # Create or update
                    obj, created_flag = WeatherForecast.objects.update_or_create(
                        city=weather_data['city'],
                        province=weather_data.get('province', ''),
                        municipality=weather_data.get('municipality', ''),
                        forecast_date=forecast_date,
                        forecast_type=forecast_type,
                        defaults=weather_data
                    )

                    if created_flag:
                        created += 1
                    else:
                        updated += 1

                    # Calculate impacts
                    obj.calculate_impacts()
                    obj.save()

                except Exception as e:
                    errors += 1
                    logger.error(f"Error processing row {start_idx + list(batch_df.index).index(row.name) + 1}: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed: {created} created, {updated} updated, {errors} errors"
            )
        )

    def map_csv_to_model(self, row, forecast_date, forecast_type):
        """Map CSV row to WeatherForecast model fields"""
        # Parse timestamp
        last_updated_epoch = row.get('last_updated_epoch', 0)
        if pd.notna(last_updated_epoch):
            # Use the CSV date for forecast_date if not specified
            forecast_date = datetime.fromtimestamp(last_updated_epoch).date()

        return {
            'city': row.get('location_name', ''),
            'province': '',  # Will be populated later by geocoding
            'municipality': '',  # Will be populated later by geocoding
            'country': row.get('country', ''),
            'latitude': row.get('latitude'),
            'longitude': row.get('longitude'),
            'forecast_type': forecast_type,
            'forecast_date': forecast_date,
            'temperature': row.get('temperature_celsius', 0),
            'feels_like': row.get('feels_like_celsius'),
            'condition': row.get('condition_text', ''),
            'humidity': row.get('humidity', 0),
            'pressure': row.get('pressure_mb', 0),
            'cloud_cover': row.get('cloud', 0),
            'wind_speed': row.get('wind_kph', 0),
            'wind_direction': row.get('wind_direction', ''),
            'wind_degree': row.get('wind_degree'),
            'gust_speed': row.get('gust_kph'),
            'precipitation': row.get('precip_mm', 0),
            'visibility': row.get('visibility_km'),
            'uv_index': row.get('uv_index', 0),
            'sunrise': row.get('sunrise', ''),
            'sunset': row.get('sunset', ''),
            'moon_phase': row.get('moon_phase', ''),
            'moon_illumination': row.get('moon_illumination'),
            'source': 'csv_dataset'
        }