"""
Management command to generate growth predictions for all active seasons.

Usage: python manage.py generate_growth_predictions
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from api.models import Season, GrowthPrediction
from api.ml_shrimp_growth import generate_growth_predictions, analyze_season_performance
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate daily growth predictions for active seasons'

    def add_arguments(self, parser):
        parser.add_argument(
            '--season-id',
            type=int,
            help='Generate predictions for specific season ID',
        )
        parser.add_argument(
            '--days-ahead',
            type=int,
            default=30,
            help='Number of days to forecast (default: 30)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without saving',
        )

    def handle(self, *args, **options):
        season_id = options.get('season_id')
        days_ahead = options.get('days_ahead')
        dry_run = options.get('dry_run')

        # Get seasons
        if season_id:
            seasons = Season.objects.filter(id=season_id, is_active=True)
            if not seasons.exists():
                raise CommandError(f'Season {season_id} not found or is not active')
        else:
            seasons = Season.objects.filter(is_active=True)

        if not seasons.exists():
            self.stdout.write(self.style.WARNING('No active seasons found'))
            return

        total_predictions = 0
        for season in seasons:
            self.stdout.write(f'\nProcessing season: {season.name} (ID: {season.id})')

            # Get latest growth metrics
            latest_metric = season.growth_metrics.order_by('-date').first()
            if not latest_metric:
                self.stdout.write(self.style.WARNING(f'  No growth metrics for season {season.name}'))
                continue

            self.stdout.write(f'  Latest metric: {latest_metric.date} - {latest_metric.avg_weight_grams}g')

            # Generate predictions
            try:
                predictions = generate_growth_predictions(season, days_ahead=days_ahead)
                
                if not predictions:
                    self.stdout.write(self.style.WARNING('  No predictions generated'))
                    continue

                self.stdout.write(self.style.SUCCESS(f'  Generated {len(predictions)} predictions'))

                if not dry_run:
                    # Deactivate previous predictions
                    GrowthPrediction.objects.filter(season=season).update(is_active=False)
                    
                    # Save new predictions
                    GrowthPrediction.objects.bulk_create(predictions, batch_size=100)
                    total_predictions += len(predictions)
                    
                    self.stdout.write(self.style.SUCCESS('  ✓ Saved to database'))
                else:
                    self.stdout.write(f'  [DRY-RUN] Would save {len(predictions)} predictions')
                    total_predictions += len(predictions)

                # Print analytics
                analytics = analyze_season_performance(season)
                if analytics:
                    self.stdout.write('  Season Analytics:')
                    self.stdout.write(f'    - Days tracked: {analytics.get("days_tracked")} days')
                    self.stdout.write(f'    - Avg daily gain: {analytics.get("average_daily_gain", 0):.2f}g/day')
                    self.stdout.write(f'    - Survival rate: {analytics.get("survival_rate", 0):.1f}%')
                    self.stdout.write(f'    - Total feed used: {analytics.get("total_feed", 0):.0f}g')

            except Exception as e:
                logger.error(f'Error processing season {season.id}: {e}', exc_info=True)
                self.stdout.write(self.style.ERROR(f'  ✗ Error: {str(e)}'))

        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n[DRY-RUN] Would create {total_predictions} predictions total'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✓ Generated {total_predictions} predictions total'))
