from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.db.models import Avg, Min, Max, Count
from datetime import datetime, time, timedelta
from collections import defaultdict
import json, csv, io, logging

from .models import (
    Report, SensorReading, Alert, FeedingLog, HistorySettings,
    Season, WeatherForecast, HarvestEntry, DailyGrowthMetric,
)
from .serializers import ReportSerializer, HarvestEntrySerializer
from .season_datasets import build_dataset_daily_rows, load_harvest_record
from .season_growth_forecast import build_season_growth_forecast

logger = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────────────

def _noon_to_noon_window(day):
    """
    Daily window 12:00 → 12:00 for `day`:
    [day 12:00, day+1 12:00).
    """
    start = timezone.make_aware(datetime.combine(day, time(12, 0, 0)))
    end = start + timedelta(days=1)
    return start, end


def _generate_report(report, user):
    """Compute summary + insights for a Report and save it."""
    start = report.start_date
    end = report.end_date

    # ── sensor data ───────────────────────────────────────────────
    # Daily reports already use noon→noon (12:00–12:00) on start/end.
    # Averages ignore NULL values for every sensor.
    if report.report_type == 'daily':
        readings = SensorReading.objects.filter(timestamp__gte=start, timestamp__lt=end)
    else:
        readings = SensorReading.objects.filter(timestamp__gte=start, timestamp__lte=end)

    sensor_agg = {
        **readings.filter(temperature__isnull=False).aggregate(
            avg_temp=Avg('temperature'), min_temp=Min('temperature'), max_temp=Max('temperature'),
            temp_count=Count('id'),
        ),
        **readings.filter(ph__isnull=False).aggregate(
            avg_ph=Avg('ph'), min_ph=Min('ph'), max_ph=Max('ph'),
            ph_count=Count('id'),
        ),
        **readings.filter(turbidity__isnull=False).aggregate(
            avg_turb=Avg('turbidity'), min_turb=Min('turbidity'), max_turb=Max('turbidity'),
            turb_count=Count('id'),
        ),
        **readings.filter(tds__isnull=False).aggregate(
            avg_tds=Avg('tds'), min_tds=Min('tds'), max_tds=Max('tds'),
            tds_count=Count('id'),
        ),
        'count': readings.count(),
    }
    sensor_data = {}
    mapping = {
        'temperature': ('avg_temp', 'min_temp', 'max_temp', 'temp_count'),
        'ph': ('avg_ph', 'min_ph', 'max_ph', 'ph_count'),
        'turbidity': ('avg_turb', 'min_turb', 'max_turb', 'turb_count'),
        'tds': ('avg_tds', 'min_tds', 'max_tds', 'tds_count'),
    }
    for key, (a, mi, ma, ck) in mapping.items():
        sensor_data[key] = {
            'avg': round(sensor_agg[a], 2) if sensor_agg[a] is not None else None,
            'min': round(sensor_agg[mi], 2) if sensor_agg[mi] is not None else None,
            'max': round(sensor_agg[ma], 2) if sensor_agg[ma] is not None else None,
            'count': sensor_agg.get(ck, 0),
        }
    if report.report_type == 'daily':
        for key in sensor_data:
            sensor_data[key]['window'] = '12:00–12:00'

    # ── alerts ────────────────────────────────────────────────────
    alerts_qs = Alert.objects.filter(timestamp__gte=start, timestamp__lte=end)
    by_param = {}
    for p in ['temperature', 'ph', 'turbidity', 'tds']:
        c = alerts_qs.filter(parameter=p).count()
        if c:
            by_param[p] = c
    alert_data = {
        'total': alerts_qs.count(),
        'by_parameter': by_param,
        'unresolved': alerts_qs.filter(resolved=False).count(),
    }

    # ── feeding ───────────────────────────────────────────────────
    feeds_qs = FeedingLog.objects.filter(timestamp__gte=start, timestamp__lte=end)
    by_type = {}
    for ft in ['manual', 'scheduled', 'weather_adjusted', 'smart_adjusted']:
        c = feeds_qs.filter(feed_type=ft).count()
        if c:
            by_type[ft] = c
    total_grams = sum(f.portion_grams for f in feeds_qs)
    feeding_data = {
        'total_events': feeds_qs.count(),
        'by_type': by_type,
        'total_grams': float(total_grams),
        'logs': [
            {
                'id': f.id,
                'timestamp': f.timestamp.isoformat(),
                'feed_type': f.feed_type,
                'portion_grams': f.portion_grams,
                'notes': f.notes or '',
            }
            for f in feeds_qs.order_by('-timestamp')[:200]
        ],
    }

    # ── period ────────────────────────────────────────────────────
    period_data = {
        'start': start.strftime('%Y-%m-%d') if hasattr(start, 'strftime') else str(start),
        'end': end.strftime('%Y-%m-%d') if hasattr(end, 'strftime') else str(end),
        'days': (end - start).days,
    }

    report.summary = {
        'sensor_data': sensor_data,
        'alerts': alert_data,
        'feeding': feeding_data,
        'period': period_data,
    }

    # ── seasonal extras: season meta, harvest, weather ────────────
    if report.report_type == 'seasonal':
        _attach_seasonal_blocks(report, start, end)

    # ── insights (rule-based) ─────────────────────────────────────
    insights = []

    # Temperature
    avg_t = sensor_data['temperature']['avg']
    if avg_t is not None:
        if avg_t > 32:
            insights.append({'type': 'critical', 'parameter': 'temperature',
                             'message': f'Average temperature {avg_t}°C exceeded safe limit (>32°C) — increase aeration'})
        elif avg_t < 26:
            insights.append({'type': 'warning', 'parameter': 'temperature',
                             'message': f'Average temperature {avg_t}°C below optimal range (26-32°C)'})
        else:
            insights.append({'type': 'info', 'parameter': 'temperature',
                             'message': f'Temperature averaged {avg_t}°C — within optimal range'})

    # pH
    avg_ph = sensor_data['ph']['avg']
    if avg_ph is not None:
        if avg_ph < 7.5 or avg_ph > 8.5:
            insights.append({'type': 'warning', 'parameter': 'ph',
                             'message': f'pH averaged {avg_ph} — outside optimal 7.5-8.5 range'})
        else:
            insights.append({'type': 'info', 'parameter': 'ph',
                             'message': f'pH remained stable at {avg_ph} within optimal range'})

    # Turbidity
    avg_turb = sensor_data['turbidity']['avg']
    if avg_turb is not None:
        if avg_turb > 3:
            insights.append({'type': 'critical', 'parameter': 'turbidity',
                             'message': f'Turbidity averaged {avg_turb} NTU — above 3 NTU, perform water change or use clarifying agents'})
        else:
            insights.append({'type': 'info', 'parameter': 'turbidity',
                             'message': f'Turbidity averaged {avg_turb} NTU — within optimal range'})

    # Feeding (IoT logs; seasonal may overwrite with pond Excel below)
    if feeding_data['total_events']:
        insights.append({'type': 'info', 'parameter': 'feeding',
                         'message': f"{feeding_data['total_events']} feeding events, {feeding_data['total_grams']:.0f}g total"})

    # Alerts
    if alert_data['total']:
        sev = 'warning' if alert_data['unresolved'] else 'info'
        insights.append({'type': sev, 'parameter': 'alerts',
                         'message': f"{alert_data['total']} alerts generated, {alert_data['unresolved']} unresolved"})

    # Seasonal harvest / weather / pond-feed insights
    if report.report_type == 'seasonal':
        feed = (report.summary or {}).get('feeding') or {}
        if feed.get('source') and feed.get('total_kg') is not None:
            # Replace IoT feeding insight with pond Excel totals
            insights = [i for i in insights if i.get('parameter') != 'feeding']
            insights.append({
                'type': 'info',
                'parameter': 'feeding',
                'message': (
                    f"Pond feed records: {feed.get('by_type', {}).get('pond_record', 0)} day(s), "
                    f"{feed['total_kg']:.1f} kg total (from feedOfSrimpDateAndAmount)."
                ),
            })
        harvest = (report.summary or {}).get('harvest') or {}
        if harvest.get('total_kg') is not None:
            insights.append({
                'type': 'info',
                'parameter': 'harvest',
                'message': (
                    f"Season harvest total {harvest.get('total_kg', 0):.2f} kg "
                    f"across {harvest.get('entry_count', 0)} entries "
                    f"({harvest.get('harvest_count', 0)} harvest events)."
                ),
            })
        weather = (report.summary or {}).get('weather') or {}
        if weather.get('days_with_data'):
            insights.append({
                'type': 'info',
                'parameter': 'weather',
                'message': (
                    f"Weather coverage: {weather['days_with_data']} day(s); "
                    f"avg air temp {weather.get('avg_temperature', '—')}°C, "
                    f"total precip {weather.get('total_precipitation_mm', '—')} mm."
                ),
            })
        gf = (report.summary or {}).get('growth_forecast') or {}
        if gf.get('predicted_harvest_kg') is not None:
            insights.append({
                'type': 'info',
                'parameter': 'growth',
                'message': (
                    f"Growth forecast: final ABW ~{gf.get('final_abw_g', '—')} g, "
                    f"predicted biomass ~{gf['predicted_harvest_kg']:.0f} kg "
                    f"({gf.get('meta', {}).get('model_version', 'model')})."
                ),
            })
        for rec in (gf.get('recommendations') or [])[:3]:
            insights.append({
                'type': rec.get('type') or 'info',
                'parameter': 'growth_recommendation',
                'message': rec.get('message', ''),
            })

    report.insights = insights
    report.status = 'completed'
    report.generated_at = timezone.now()
    report.save()
    return report


def _attach_seasonal_blocks(report, start, end):
    """Attach season / harvest / weather blocks into report.summary (in place)."""
    summary = report.summary if isinstance(report.summary, dict) else {}
    data = report.data if isinstance(report.data, dict) else {}
    season_id = data.get('season_id')
    season = None
    if season_id:
        season = Season.objects.filter(id=season_id).first()

    start_d = timezone.localtime(start).date() if timezone.is_aware(start) else start.date()
    end_d = timezone.localtime(end).date() if timezone.is_aware(end) else end.date()

    if season:
        entries = list(season.entries.all().order_by('date', 'id'))
        summary['season'] = {
            'id': season.id,
            'name': season.name,
            'start_date': str(season.start_date),
            'end_date': str(season.end_date) if season.end_date else None,
            'is_active': season.is_active,
            'stocking_density': season.stocking_density,
            'initial_shrimp_quantity': season.initial_shrimp_quantity,
            'current_shrimp_quantity': season.current_shrimp_quantity,
            'average_shrimp_weight_grams': season.average_shrimp_weight_grams,
            'notes': season.notes or '',
            'days_active': (
                ((season.end_date or timezone.localdate()) - season.start_date).days + 1
            ),
        }
        summary['harvest'] = {
            'total_kg': float(season.total_harvest_kg or 0),
            'harvest_count': int(season.harvest_count or 0),
            'entry_count': int(season.entry_count or 0),
            'entries': HarvestEntrySerializer(entries, many=True).data,
        }
    else:
        summary['season'] = None
        summary['harvest'] = {'total_kg': 0, 'harvest_count': 0, 'entry_count': 0, 'entries': []}

    weather_qs = WeatherForecast.objects.filter(
        forecast_date__gte=start_d,
        forecast_date__lte=end_d,
    ).order_by('forecast_date')
    weather_agg = weather_qs.aggregate(
        avg_temperature=Avg('temperature'),
        min_temperature=Min('temperature'),
        max_temperature=Max('temperature'),
        avg_humidity=Avg('humidity'),
        days=Count('id'),
    )
    precip_vals = list(weather_qs.values_list('precipitation', flat=True))
    total_precip = float(sum(p or 0 for p in precip_vals)) if precip_vals else 0.0
    # Deduplicate by date for a compact daily list
    by_date = {}
    for w in weather_qs:
        key = str(w.forecast_date)
        if key not in by_date:
            by_date[key] = {
                'date': key,
                'temperature': w.temperature,
                'min_temperature': w.min_temperature,
                'max_temperature': w.max_temperature,
                'condition': w.condition,
                'humidity': w.humidity,
                'precipitation': w.precipitation,
                'wind_speed': w.wind_speed,
                'city': w.city,
            }
    summary['weather'] = {
        'days_with_data': weather_agg['days'] or 0,
        'avg_temperature': round(weather_agg['avg_temperature'], 2) if weather_agg['avg_temperature'] is not None else None,
        'min_temperature': round(weather_agg['min_temperature'], 2) if weather_agg['min_temperature'] is not None else None,
        'max_temperature': round(weather_agg['max_temperature'], 2) if weather_agg['max_temperature'] is not None else None,
        'avg_humidity': round(weather_agg['avg_humidity'], 1) if weather_agg['avg_humidity'] is not None else None,
        'total_precipitation_mm': round(total_precip, 2),
        'daily': list(by_date.values())[:120],
    }

    # Per-calendar-day rows for Excel: prefer dataset Excels (feed/weather/harvest),
    # then merge live DB sensor/feed/harvest when present for that same date.
    summary['daily_rows'] = _build_season_daily_rows(start, end, season, by_date)
    summary['totals'] = _season_daily_totals(summary['daily_rows'])

    # Prefer pond feed sheets over empty IoT FeedingLog for historical seasons
    _attach_dataset_feeding(summary)

    # Prefer actual harvest total from harvests/ Excel when available
    try:
        actual = load_harvest_record(start_d, end_d)
        if actual and actual.get('harvest_kg') is not None:
            summary.setdefault('harvest', {})
            summary['harvest']['total_kg'] = actual['harvest_kg']
            summary['harvest']['source_file'] = actual.get('file')
            summary['harvest']['close_date'] = (
                actual['close_date'].isoformat() if actual.get('close_date') else None
            )
            summary['totals']['total_harvest_kg'] = actual['harvest_kg']
            # Keep History DB aligned with actual harvest sheet
            if season is not None:
                close = actual.get('close_date') or end_d
                if close < start_d or close > end_d:
                    close = end_d
                HarvestEntry.objects.filter(season=season).delete()
                HarvestEntry.objects.create(
                    season=season,
                    date=close,
                    amount=float(actual['harvest_kg']),
                    unit='kg',
                    note=f"Actual harvest from {actual.get('file')}",
                    is_all=True,
                )
                season.recompute_totals()
    except Exception as exc:
        logger.warning('Failed to attach actual harvest sheet data: %s', exc)

    # If DB weather is empty, expose open-meteo daily weather from daily_rows
    if not summary.get('weather', {}).get('days_with_data'):
        wx_days = [
            {
                'date': r['date'],
                'temperature': r.get('weather_temperature'),
                'condition': r.get('weather_condition'),
                'humidity': r.get('weather_humidity'),
                'precipitation': r.get('weather_precipitation_mm'),
            }
            for r in summary['daily_rows']
            if r.get('weather_temperature') is not None
        ]
        if wx_days:
            temps = [d['temperature'] for d in wx_days if d['temperature'] is not None]
            precip = [d['precipitation'] or 0 for d in wx_days]
            hum = [d['humidity'] for d in wx_days if d['humidity'] is not None]
            summary['weather'] = {
                'days_with_data': len(wx_days),
                'avg_temperature': round(sum(temps) / len(temps), 2) if temps else None,
                'min_temperature': round(min(temps), 2) if temps else None,
                'max_temperature': round(max(temps), 2) if temps else None,
                'avg_humidity': round(sum(hum) / len(hum), 1) if hum else None,
                'total_precipitation_mm': round(sum(precip), 2),
                'daily': wx_days[:120],
                'source': 'dataset/weatherForShrimpFeedingDate',
            }

    # Growth forecast analytics (daily ABW curve + harvest + recommendations)
    try:
        # Prefer actual harvest kg already attached from harvests/ Excel
        if season is not None and summary.get('harvest', {}).get('total_kg'):
            try:
                season.total_harvest_kg = float(summary['harvest']['total_kg'])
            except (TypeError, ValueError):
                pass
        forecast = build_season_growth_forecast(
            season,
            summary.get('daily_rows') or [],
            start_d=start_d,
            end_d=end_d,
        )
        if forecast:
            # Keep payload lean for API — full table available but series is primary for charts
            summary['growth_forecast'] = {
                'abw_series': forecast['abw_series'],
                'feature_table_preview': forecast['feature_table'][:14],
                'feature_table_days': len(forecast['feature_table']),
                'predicted_harvest_kg': forecast['predicted_harvest_kg'],
                'actual_harvest_kg': forecast.get('actual_harvest_kg'),
                'final_abw_g': forecast['final_abw_g'],
                'target_abw_g': forecast['target_abw_g'],
                'days_to_target_abw': forecast['days_to_target_abw'],
                'estimated_harvest_date': forecast['estimated_harvest_date'],
                'initial_stock': forecast['initial_stock'],
                'recommendations': forecast['recommendations'],
                'meta': forecast['meta'],
                # Full daily features for Excel / advanced UI (cap very long seasons)
                'feature_table': forecast['feature_table'],
            }
    except Exception as exc:
        logger.warning('Failed to build season growth forecast: %s', exc)
        summary['growth_forecast'] = None

    report.summary = summary


def _attach_dataset_feeding(summary):
    """Fill summary.feeding from feedOfSrimpDateAndAmount via daily_rows."""
    daily = summary.get('daily_rows') or []
    feed_days = [r for r in daily if r.get('feed_kg') is not None]
    if not feed_days:
        return

    total_kg = round(sum(float(r['feed_kg']) for r in feed_days), 2)
    total_events = sum(int(r.get('feed_events') or 0) for r in feed_days)
    existing = summary.get('feeding') if isinstance(summary.get('feeding'), dict) else {}
    db_events = int(existing.get('total_events') or 0)

    # Prefer pond Excel when it has more coverage than IoT feeder logs
    if len(feed_days) >= db_events:
        summary['feeding'] = {
            'total_events': total_events or len(feed_days),
            'by_type': {'pond_record': len(feed_days)},
            'total_kg': total_kg,
            'total_grams': round(total_kg * 1000.0, 1),
            'source': 'dataset/feedOfSrimpDateAndAmount',
            'unit': 'kg',
            'logs': [
                {
                    'id': f"feed-{r['date']}",
                    'timestamp': f"{r['date']}T12:00:00",
                    'feed_type': 'pond_record',
                    'portion_kg': r['feed_kg'],
                    'portion_grams': round(float(r['feed_kg']) * 1000.0, 1),
                    'notes': f"Daily total from pond feed sheet ({r.get('feed_events') or 5} slots)",
                }
                for r in feed_days
            ],
        }
    else:
        existing['total_kg'] = round(float(existing.get('total_grams') or 0) / 1000.0, 3)
        summary['feeding'] = existing


def _avg_or_none(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 2)


def _harvest_amount_kg(amount, unit):
    try:
        amt = float(amount or 0)
    except (TypeError, ValueError):
        return 0.0
    unit = (unit or 'kg').lower()
    if unit in ('tonne', 'tonnes', 'ton', 'tons'):
        return amt * 1000.0
    if unit in ('piece', 'pieces', 'pcs'):
        return 0.0
    return amt


def _build_season_daily_rows(start, end, season, weather_by_date):
    """
    Merge:
      1) dataset Excel files (feed / open-meteo weather / actual harvest)
      2) DB sensors + feeding logs + harvest entries for the same dates
    Empty cell when that date has no matching value.
    """
    start_d = timezone.localtime(start).date() if timezone.is_aware(start) else start.date()
    end_d = timezone.localtime(end).date() if timezone.is_aware(end) else end.date()

    # --- Dataset files (primary for historical seasons) ---
    dataset_rows, meta = build_dataset_daily_rows(start_d, end_d)
    by_day = {r['date']: dict(r) for r in dataset_rows}

    # --- DB sensors ---
    sensor_buckets = defaultdict(lambda: {
        'temperature': [], 'ph': [], 'turbidity': [], 'tds': [],
    })
    readings = SensorReading.objects.filter(
        timestamp__gte=start, timestamp__lte=end,
    ).only('timestamp', 'temperature', 'ph', 'turbidity', 'tds')
    for r in readings.iterator():
        day = timezone.localtime(r.timestamp).date() if timezone.is_aware(r.timestamp) else r.timestamp.date()
        key = day.isoformat()
        if r.temperature is not None:
            sensor_buckets[key]['temperature'].append(float(r.temperature))
        if r.ph is not None:
            sensor_buckets[key]['ph'].append(float(r.ph))
        if r.turbidity is not None:
            sensor_buckets[key]['turbidity'].append(float(r.turbidity))
        if r.tds is not None:
            sensor_buckets[key]['tds'].append(float(r.tds))

    # --- DB feeds (grams) — only used if dataset feed missing that day ---
    feed_db = defaultdict(lambda: {'grams': 0.0, 'events': 0})
    for f in FeedingLog.objects.filter(timestamp__gte=start, timestamp__lte=end).only('timestamp', 'portion_grams').iterator():
        day = timezone.localtime(f.timestamp).date() if timezone.is_aware(f.timestamp) else f.timestamp.date()
        key = day.isoformat()
        feed_db[key]['grams'] += float(f.portion_grams or 0)
        feed_db[key]['events'] += 1

    # --- DB harvest fallback ---
    harvest_db = defaultdict(float)
    if season is not None:
        for e in season.entries.all().only('date', 'amount', 'unit'):
            if e.date is None or not (start_d <= e.date <= end_d):
                continue
            harvest_db[e.date.isoformat()] += _harvest_amount_kg(e.amount, e.unit)

    # --- Daily shrimp quantity from Growth Dashboard metrics (leave blank if none) ---
    shrimp_by_day = {}
    if season is not None:
        for m in DailyGrowthMetric.objects.filter(
            season=season,
            date__gte=start_d,
            date__lte=end_d,
        ).only('date', 'shrimp_count', 'avg_weight_grams').iterator():
            key = m.date.isoformat()
            shrimp_by_day[key] = {
                'shrimp_count': int(m.shrimp_count) if m.shrimp_count is not None else None,
                'avg_weight_grams': (
                    float(m.avg_weight_grams) if m.avg_weight_grams is not None else None
                ),
            }

    # Ensure every day that has DB-only data also appears
    all_keys = set(by_day.keys()) | set(sensor_buckets.keys()) | set(feed_db.keys()) | set(harvest_db.keys())
    # Also include DB weather forecast keys if present
    all_keys |= set(weather_by_date.keys())
    all_keys |= set(shrimp_by_day.keys())

    rows = []
    for key in sorted(all_keys):
        try:
            d = datetime.fromisoformat(key).date()
        except ValueError:
            continue
        if d < start_d or d > end_d:
            continue

        base = by_day.get(key, {
            'date': key,
            'avg_temperature': None, 'avg_ph': None, 'avg_turbidity': None, 'avg_tds': None,
            'weather_temperature': None, 'weather_condition': None,
            'weather_precipitation_mm': None, 'weather_humidity': None,
            'feed_kg': None, 'feed_events': None, 'harvest_kg': None,
            'shrimp_count': None, 'avg_weight_grams': None,
        })

        sensors = sensor_buckets.get(key)
        if sensors and any(sensors[k] for k in sensors):
            base['avg_temperature'] = _avg_or_none(sensors['temperature'])
            base['avg_ph'] = _avg_or_none(sensors['ph'])
            base['avg_turbidity'] = _avg_or_none(sensors['turbidity'])
            base['avg_tds'] = _avg_or_none(sensors['tds'])

        # DB WeatherForecast fallback if dataset weather missing
        if base.get('weather_temperature') is None and key in weather_by_date:
            w = weather_by_date[key]
            base['weather_temperature'] = w.get('temperature')
            base['weather_condition'] = w.get('condition')
            base['weather_precipitation_mm'] = w.get('precipitation')
            base['weather_humidity'] = w.get('humidity')

        # Dataset feed is kg; DB feed is grams → convert to kg if needed
        if base.get('feed_kg') is None and key in feed_db and feed_db[key]['events'] > 0:
            base['feed_kg'] = round(feed_db[key]['grams'] / 1000.0, 3)
            base['feed_events'] = feed_db[key]['events']

        if base.get('harvest_kg') is None and key in harvest_db and harvest_db[key] > 0:
            base['harvest_kg'] = round(harvest_db[key], 3)

        # Growth metric shrimp qty — only when saved that day (do not invent values)
        g = shrimp_by_day.get(key)
        if g:
            if base.get('shrimp_count') is None:
                base['shrimp_count'] = g.get('shrimp_count')
            if base.get('avg_weight_grams') is None:
                base['avg_weight_grams'] = g.get('avg_weight_grams')

        has_any = any([
            base.get('avg_temperature') is not None,
            base.get('avg_ph') is not None,
            base.get('avg_turbidity') is not None,
            base.get('avg_tds') is not None,
            base.get('weather_temperature') is not None,
            base.get('feed_kg') is not None,
            base.get('harvest_kg') is not None,
            base.get('shrimp_count') is not None,
        ])
        if not has_any:
            continue

        # Drop internal source markers from export rows
        rows.append({
            'date': base['date'],
            'avg_temperature': base.get('avg_temperature'),
            'avg_ph': base.get('avg_ph'),
            'avg_turbidity': base.get('avg_turbidity'),
            'avg_tds': base.get('avg_tds'),
            'weather_temperature': base.get('weather_temperature'),
            'weather_condition': base.get('weather_condition'),
            'weather_precipitation_mm': base.get('weather_precipitation_mm'),
            'weather_humidity': base.get('weather_humidity'),
            'feed_kg': base.get('feed_kg'),
            'feed_events': base.get('feed_events'),
            'harvest_kg': base.get('harvest_kg'),
            'shrimp_count': base.get('shrimp_count'),
            'avg_weight_grams': base.get('avg_weight_grams'),
        })

    # stash source meta on first row via logger
    if meta:
        logger.info(
            'Season daily rows sources: feed=%s harvest=%s days=%s',
            meta.get('feed_file'), (meta.get('harvest') or {}).get('file'), len(rows),
        )
    return rows


def _season_daily_totals(daily_rows):
    def _sum(key):
        vals = [r[key] for r in daily_rows if r.get(key) is not None]
        return round(sum(vals), 2) if vals else None

    return {
        'days_with_data': len(daily_rows),
        'total_feed_kg': _sum('feed_kg'),
        'total_feed_events': _sum('feed_events'),
        'total_harvest_kg': _sum('harvest_kg'),
        'avg_weather_temperature': _avg_or_none([r.get('weather_temperature') for r in daily_rows]),
        'avg_temperature': _avg_or_none([r['avg_temperature'] for r in daily_rows]),
        'avg_ph': _avg_or_none([r['avg_ph'] for r in daily_rows]),
        'avg_turbidity': _avg_or_none([r['avg_turbidity'] for r in daily_rows]),
        'avg_tds': _avg_or_none([r['avg_tds'] for r in daily_rows]),
    }


def _email_report(report, email):
    """Send an HTML email with the report and a CSV attachment."""
    from django.core.mail import EmailMessage
    from django.conf import settings as django_settings

    # Validate email address
    if not email or '@' not in email:
        raise ValueError(f'Invalid email address: {email}')

    summary = report.summary if isinstance(report.summary, dict) else json.loads(report.summary or '{}')
    insights = report.insights if isinstance(report.insights, list) else json.loads(report.insights or '[]')
    sd = summary.get('sensor_data', {})
    period = summary.get('period', {})

    # Build HTML body
    rows_html = ''
    for key, label, unit in [
        ('temperature', 'Temperature', '°C'), ('ph', 'pH', ''),
        ('turbidity', 'Turbidity', 'NTU'), ('tds', 'TDS', 'ppm'),
    ]:
        d = sd.get(key, {})
        avg = d.get('avg', '—')
        mn = d.get('min', '—')
        mx = d.get('max', '—')
        rows_html += f'<tr><td style="padding:8px;border:1px solid #e5e7eb">{label}</td>'
        rows_html += f'<td style="padding:8px;border:1px solid #e5e7eb">{avg} {unit}</td>'
        rows_html += f'<td style="padding:8px;border:1px solid #e5e7eb">{mn}</td>'
        rows_html += f'<td style="padding:8px;border:1px solid #e5e7eb">{mx}</td></tr>'

    insights_html = ''
    colors = {'critical': '#fecaca', 'warning': '#fef3c7', 'info': '#dbeafe'}
    for ins in insights:
        bg = colors.get(ins.get('type', 'info'), '#f3f4f6')
        insights_html += (
            f'<div style="background:{bg};padding:10px 14px;border-radius:8px;margin-bottom:6px">'
            f'<strong>{ins.get("parameter","").replace("_"," ").title()}</strong>: {ins.get("message","")}</div>'
        )

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:auto">
      <div style="background:linear-gradient(135deg,#0ea5e9,#0284c7);color:#fff;padding:20px 24px;border-radius:12px 12px 0 0">
        <h2 style="margin:0">🦐 {report.title}</h2>
        <p style="margin:4px 0 0;opacity:.85">{period.get('start','')} — {period.get('end','')}</p>
      </div>
      <div style="padding:20px 24px;border:1px solid #e5e7eb;border-top:none">
        <h3>Sensor Summary</h3>
        <table style="width:100%;border-collapse:collapse">
          <tr style="background:#f0f9ff"><th style="padding:8px;border:1px solid #e5e7eb;text-align:left">Parameter</th>
          <th style="padding:8px;border:1px solid #e5e7eb">Avg</th>
          <th style="padding:8px;border:1px solid #e5e7eb">Min</th>
          <th style="padding:8px;border:1px solid #e5e7eb">Max</th></tr>
          {rows_html}
        </table>
        <h3 style="margin-top:18px">Insights</h3>
        {insights_html}
        <p style="text-align:center;color:#9ca3af;font-size:12px;margin-top:24px">
          Generated by ShrimplySmart &copy; {timezone.now().year}
        </p>
      </div>
    </div>
    """

    # Build CSV attachment of raw sensor readings
    start = report.start_date
    end = report.end_date
    readings = SensorReading.objects.filter(timestamp__gte=start, timestamp__lte=end).order_by('timestamp')
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Timestamp', 'Temperature', 'pH', 'Turbidity', 'TDS'])
    for r in readings[:2000]:  # cap at 2000 rows
        writer.writerow([r.timestamp.isoformat(), r.temperature, r.ph, r.turbidity, r.tds])
    csv_bytes = buf.getvalue().encode('utf-8')

    try:
        msg = EmailMessage(
            subject=report.title,
            body=html,
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.content_subtype = 'html'
        msg.attach(f'sensor_data_{period.get("start","")}.csv', csv_bytes, 'text/csv')
        result = msg.send(fail_silently=False)
        logger.info(f'Email sent to {email}: {result} message(s) sent')
    except Exception as e:
        logger.error(f'Failed to send email to {email}: {str(e)}')
        raise


# ── ViewSet ────────────────────────────────────────────────────────────

class ReportPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


class ReportViewSet(viewsets.ModelViewSet):
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ReportPagination

    def get_queryset(self):
        return Report.objects.all().order_by('-generated_at', '-id')

    # ── generate helpers ──────────────────────────────────────────

    def _create_and_generate(self, title, report_type, start_dt, end_dt, user, data=None):
        report = Report.objects.create(
            title=title, report_type=report_type,
            start_date=start_dt, end_date=end_dt, status='generating',
            data=data or {},
        )
        _generate_report(report, user)
        return Response(ReportSerializer(report).data, status=201)

    @action(detail=False, methods=['post'])
    def generate_daily(self, request):
        date_str = request.data.get('date')
        if date_str:
            d = datetime.fromisoformat(str(date_str)[:10]).date()
        else:
            d = timezone.localdate()
        # Daily window is noon-to-noon (12:00 → next day 12:00)
        start, end = _noon_to_noon_window(d)
        return self._create_and_generate(
            f"Daily Report — {d.strftime('%B %d, %Y')} (12:00–12:00)", 'daily', start, end, request.user,
        )

    @action(detail=False, methods=['post'])
    def generate_weekly(self, request):
        end = timezone.now()
        start = end - timedelta(days=7)
        if request.data.get('start_date'):
            start = timezone.datetime.fromisoformat(request.data['start_date'])
        if request.data.get('end_date'):
            end = timezone.datetime.fromisoformat(request.data['end_date'])
        return self._create_and_generate(
            f"Weekly Report — {start.strftime('%b %d')} to {end.strftime('%b %d, %Y')}",
            'weekly', start, end, request.user,
        )

    @action(detail=False, methods=['post'])
    def generate_monthly(self, request):
        now = timezone.now()
        year = int(request.data.get('year', now.year))
        month = int(request.data.get('month', now.month))
        start = timezone.make_aware(timezone.datetime(year, month, 1))
        end = (timezone.make_aware(timezone.datetime(year + (1 if month == 12 else 0),
               (month % 12) + 1, 1)) - timedelta(seconds=1))
        return self._create_and_generate(
            f"Monthly Report — {start.strftime('%B %Y')}", 'monthly', start, end, request.user,
        )

    @action(detail=False, methods=['post'])
    def generate_custom(self, request):
        start = datetime.fromisoformat(str(request.data['start_date']))
        end = datetime.fromisoformat(str(request.data['end_date']))
        if timezone.is_naive(start):
            start = timezone.make_aware(start)
        if timezone.is_naive(end):
            end = timezone.make_aware(end)
        title = request.data.get('title',
                    f"Custom Report — {start.strftime('%b %d')} to {end.strftime('%b %d, %Y')}")
        return self._create_and_generate(title, 'custom', start, end, request.user)

    @action(detail=False, methods=['post'])
    def generate_seasonal(self, request):
        """Generate a full season report: sensors, weather, feeding logs, harvest."""
        season_id = request.data.get('season_id')
        if not season_id:
            return Response({'error': 'season_id is required'}, status=400)
        season = Season.objects.filter(id=season_id, user=request.user).first()
        if not season:
            # Allow staff / shared seasons without user filter as fallback
            season = Season.objects.filter(id=season_id).first()
        if not season:
            return Response({'error': 'Season not found'}, status=404)

        end_date = season.end_date or timezone.localdate()
        start = timezone.make_aware(datetime.combine(season.start_date, time.min))
        end = timezone.make_aware(datetime.combine(end_date, time.max))
        title = request.data.get(
            'title',
            f"Seasonal Report — {season.name} ({season.start_date} → {end_date})",
        )
        return self._create_and_generate(
            title, 'seasonal', start, end, request.user,
            data={'season_id': season.id},
        )

    @action(detail=True, methods=['post'])
    def regenerate(self, request, pk=None):
        report = self.get_object()
        report.status = 'generating'
        report.save()
        _generate_report(report, request.user)
        return Response(ReportSerializer(report).data)

    @action(detail=False, methods=['get'])
    def recent(self, request):
        limit = int(request.query_params.get('limit', 10))
        qs = Report.objects.all()[:limit]
        return Response(ReportSerializer(qs, many=True).data)

    # ── email action ──────────────────────────────────────────────
    @action(detail=True, methods=['post'])
    def email(self, request, pk=None):
        report = self.get_object()
        email = request.data.get('email', '')
        if not email:
            # fallback to HistorySettings
            hs = HistorySettings.objects.filter(user=request.user).first()
            email = hs.notification_email if hs else ''
        if not email:
            return Response({'error': 'No email address provided'}, status=400)
        try:
            _email_report(report, email)
            return Response({'status': 'sent', 'email': email})
        except Exception as exc:
            logger.exception('Email report failed')
            return Response({'error': f'Failed to send: {exc}'}, status=500)
