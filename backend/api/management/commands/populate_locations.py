from django.core.management.base import BaseCommand
from api.models import WeatherForecast
import pandas as pd
import requests
import time
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Populate province and municipality data for weather forecasts using reverse geocoding'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of records to process in each batch'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.0,
            help='Delay in seconds between API calls'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of records to process (for testing)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        delay = options['delay']
        limit = options['limit']
        dry_run = options['dry_run']

        # Get forecasts that need location data
        forecasts = WeatherForecast.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False,
            province='',
            municipality=''
        )

        if limit:
            forecasts = forecasts[:limit]

        total = forecasts.count()
        self.stdout.write(f"Found {total} forecasts to update")

        if dry_run:
            self.stdout.write("DRY RUN - No changes will be made")

        updated = 0
        errors = 0

        for i, forecast in enumerate(forecasts.iterator()):
            if i % batch_size == 0:
                self.stdout.write(f"Processing batch {i//batch_size + 1}...")

            try:
                # Reverse geocode
                location_data = self.reverse_geocode(forecast.latitude, forecast.longitude)

                if location_data:
                    province = location_data.get('province', '')
                    municipality = location_data.get('municipality', '')

                    if dry_run:
                        self.stdout.write(f"Would update {forecast.city}: province='{province}', municipality='{municipality}'")
                    else:
                        forecast.province = province
                        forecast.municipality = municipality
                        forecast.save(update_fields=['province', 'municipality'])
                        updated += 1

                else:
                    errors += 1
                    self.stdout.write(f"Failed to geocode {forecast.city} ({forecast.latitude}, {forecast.longitude})")

            except Exception as e:
                errors += 1
                logger.error(f"Error processing {forecast.city}: {e}")

            # Rate limiting
            if delay > 0:
                time.sleep(delay)

        self.stdout.write(
            self.style.SUCCESS(f"Completed: {updated} updated, {errors} errors")
        )

    def reverse_geocode(self, lat, lon):
        """Reverse geocode using Nominatim API"""
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            'format': 'json',
            'lat': lat,
            'lon': lon,
            'zoom': 10,  # Get administrative details
            'addressdetails': 1
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            address = data.get('address', {})

            # Extract province/state and municipality
            province = (
                address.get('state') or
                address.get('province') or
                address.get('region') or
                ''
            )

            municipality = (
                address.get('city') or
                address.get('town') or
                address.get('village') or
                address.get('municipality') or
                address.get('county') or
                ''
            )

            return {
                'province': province,
                'municipality': municipality
            }

        except requests.RequestException as e:
            logger.error(f"Geocoding error for {lat},{lon}: {e}")
            return None