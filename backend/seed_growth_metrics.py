#!/usr/bin/env python
"""Seed DailyGrowthMetric data for a Season.

Usage:
  python seed_growth_metrics.py --season-id 9 --days 10

This is a dev utility to quickly create enough metrics to exercise the growth
analytics + prediction pipeline.
"""

import argparse
import os
import sys
from datetime import date, timedelta

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aquaculture_api.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from api.models import Season, DailyGrowthMetric  # noqa: E402


def _round2(x: float) -> float:
    return float(f"{x:.2f}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--season-id', type=int, required=True)
    parser.add_argument('--days', type=int, default=10)
    parser.add_argument('--daily-gain', type=float, default=0.25)
    parser.add_argument('--daily-mortality-percent', type=float, default=0.2)
    parser.add_argument('--water-temperature', type=float, default=28.0)
    parser.add_argument('--water-ph', type=float, default=7.5)
    parser.add_argument('--dissolved-oxygen', type=float, default=6.5)
    parser.add_argument('--tds', type=float, default=1200.0)
    parser.add_argument('--weather-condition', type=str, default='clear')
    args = parser.parse_args()

    season = Season.objects.filter(id=args.season_id).first()
    if not season:
        print(f"✗ Season not found: id={args.season_id}")
        return 1

    start_count = int(season.current_shrimp_quantity or 50000)
    start_weight = float(season.average_shrimp_weight_grams or 2.5)

    # Create metrics for the last N days ending today.
    days = max(1, int(args.days))
    start_date = date.today() - timedelta(days=days - 1)

    created = 0
    updated = 0

    for i in range(days):
        d = start_date + timedelta(days=i)

        # Simple deterministic progression for demo purposes.
        avg_weight = start_weight + (args.daily_gain * i)
        if i == 0:
            daily_gain = 0.0
        else:
            daily_gain = float(args.daily_gain)

        survival_factor = (1.0 - (float(args.daily_mortality_percent) / 100.0)) ** i
        shrimp_count = max(0, int(round(start_count * survival_factor)))

        # Feed ~3% of biomass per day (biomass grams = count * grams/shrimp)
        biomass_grams = shrimp_count * avg_weight
        feed_amount = 0.03 * biomass_grams

        obj, was_created = DailyGrowthMetric.objects.update_or_create(
            season=season,
            date=d,
            defaults={
                'shrimp_count': shrimp_count,
                'avg_weight_grams': _round2(avg_weight),
                'daily_weight_gain_grams': _round2(daily_gain),
                'daily_mortality_percent': _round2(float(args.daily_mortality_percent)),
                'feed_amount_grams': _round2(feed_amount),
                'water_temperature': float(args.water_temperature),
                'water_ph': float(args.water_ph),
                'dissolved_oxygen': float(args.dissolved_oxygen),
                'tds': float(args.tds),
                'weather_condition': str(args.weather_condition),
                'notes': 'Seeded demo metric',
            },
        )

        if was_created:
            created += 1
        else:
            updated += 1

    print(
        f"✓ Seeded DailyGrowthMetric for season {season.id} ({season.name}) "
        f"user_id={season.user_id}: created={created}, updated={updated}, days={days}"
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
