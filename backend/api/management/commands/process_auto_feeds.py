"""
Management command to process auto-feeds due for execution.

Usage:
  python manage.py process_auto_feeds

Schedule this with cron or Windows Task Scheduler every minute:
  * * * * * cd /path/to/backend && python manage.py process_auto_feeds
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from api.models import Feeder, FeedingLog, WeatherCache
from api.feeder_servo_scheduler import enqueue_servo_job
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process any due auto-feed events for all active feeders'

    def handle(self, *args, **options):
        now = timezone.now()
        feeders = Feeder.objects.filter(auto_enabled=True, next_feed_at__lte=now)

        if not feeders.exists():
            self.stdout.write('No feeders due for auto-feeding.')
            return

        for feeder in feeders:
            if feeder.capacity_current <= 0:
                self.stdout.write(self.style.WARNING(f'Feeder {feeder.id}: empty — skipping'))
                continue

            # Weather check
            weather_data = None
            if feeder.weather_adaptation:
                weather_data = WeatherCache.get_weather('Oriental Mindoro')

            if not feeder.should_feed_based_on_weather(weather_data):
                self.stdout.write(self.style.WARNING(f'Feeder {feeder.id}: paused by weather'))
                # Still advance schedule so it doesn't pile up
                feeder.next_feed_at = feeder.get_next_feed_time()
                feeder.save()
                continue

            # Calculate portion
            portion = feeder.adjust_portion_for_weather(feeder.portion_grams, weather_data)
            portion = min(portion, feeder.capacity_current)

            capacity_before = feeder.capacity_current
            feeder.capacity_current -= portion
            feeder.last_fed_at = now
            feeder.next_feed_at = feeder.get_next_feed_time()
            feeder.save()

            feed_type = 'weather_adjusted' if (weather_data and feeder.weather_adaptation) else 'scheduled'
            FeedingLog.objects.create(
                feeder=feeder,
                feed_type=feed_type,
                portion_grams=portion,
                capacity_before=capacity_before,
                capacity_after=feeder.capacity_current,
                weather_conditions=weather_data,
                notes=f'Auto ({feed_type}): {portion}g dispensed',
            )

            # Schedule servo ON now and OFF after computed duration.
            enqueue_servo_job(target_grams=portion, on_at=now, device_id="wemos-poller")

            self.stdout.write(self.style.SUCCESS(
                f'Feeder {feeder.id}: dispensed {portion}g ({feed_type}) — '
                f'{feeder.capacity_current}g remaining'
            ))
