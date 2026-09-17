from django.core.management.base import BaseCommand
from api.models import Threshold

class Command(BaseCommand):
    help = 'Populate default sensor thresholds'

    def handle(self, *args, **options):
        # Derived from Normal-class samples in
        # possible_dataset/fishpond_dataset_multiclass_2153.csv
        # (see frontend/src/services/settings.js DEFAULT_THRESHOLDS).
        defaults = [
            {'parameter': 'temperature', 'min_value': 25, 'max_value': 30, 'unit': '°C'},
            {'parameter': 'ph', 'min_value': 6.5, 'max_value': 8.5, 'unit': ''},
            {'parameter': 'turbidity', 'min_value': 1, 'max_value': 25, 'unit': 'NTU'},
            {'parameter': 'tds', 'min_value': 20, 'max_value': 325, 'unit': 'ppm'},
        ]

        for threshold_data in defaults:
            threshold, created = Threshold.objects.update_or_create(
                parameter=threshold_data['parameter'],
                defaults={
                    'min_value': threshold_data['min_value'],
                    'max_value': threshold_data['max_value'],
                    'unit': threshold_data['unit']
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✅ Created threshold for {threshold.parameter}: {threshold.min_value}-{threshold.max_value} {threshold.unit}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'✅ Updated threshold for {threshold.parameter}: {threshold.min_value}-{threshold.max_value} {threshold.unit}'))