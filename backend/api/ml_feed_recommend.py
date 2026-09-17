"""
Weather + growth adaptive feed recommendation (kg / day + time slots).

Uses model trained from feed charts + Calapan Open-Meteo weather + harvest metadata,
then scales by live Growth Dashboard quantity / average weight (biomass).
"""
from __future__ import annotations

import logging
import math
import pickle
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import requests

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent / "ml_models" / "feed_recommender_v1.pkl"
CALAPAN_LAT = 13.3216
CALAPAN_LON = 121.1507

# Typical mid-culture reference used to scale vs Growth Dashboard biomass
REF_STOCKS = 250_000.0
REF_ABW_G = 8.0

_BUNDLE = None


def _load_bundle():
    global _BUNDLE
    if _BUNDLE is not None:
        return _BUNDLE
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Feed model missing: {MODEL_PATH}")
    with open(MODEL_PATH, "rb") as f:
        _BUNDLE = pickle.load(f)
    return _BUNDLE


def fetch_today_weather(lat: float = CALAPAN_LAT, lon: float = CALAPAN_LON) -> dict[str, float]:
    """Daily aggregates from Open-Meteo forecast API for Calapan."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
        "relative_humidity_2m_mean,precipitation_sum,rain_sum,"
        "surface_pressure_mean,cloud_cover_mean,wind_speed_10m_mean"
        "&timezone=Asia%2FManila&forecast_days=1"
    )
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        daily = r.json().get("daily", {})
        return {
            "temp_mean": float(daily.get("temperature_2m_mean", [28])[0] or 28),
            "temp_max": float(daily.get("temperature_2m_max", [31])[0] or 31),
            "temp_min": float(daily.get("temperature_2m_min", [24])[0] or 24),
            "humidity_mean": float(daily.get("relative_humidity_2m_mean", [80])[0] or 80),
            "rain_sum": float(daily.get("rain_sum", [0])[0] or 0),
            "precip_sum": float(daily.get("precipitation_sum", [0])[0] or 0),
            "pressure_mean": float(daily.get("surface_pressure_mean", [1010])[0] or 1010),
            "cloud_mean": float(daily.get("cloud_cover_mean", [50])[0] or 50),
            "wind_mean": float(daily.get("wind_speed_10m_mean", [5])[0] or 5),
            "source": "open-meteo",
        }
    except Exception as e:
        logger.warning("Open-Meteo fetch failed, using defaults: %s", e)
        return {
            "temp_mean": 28.0,
            "temp_max": 31.0,
            "temp_min": 24.0,
            "humidity_mean": 80.0,
            "rain_sum": 0.0,
            "precip_sum": 0.0,
            "pressure_mean": 1010.0,
            "cloud_mean": 50.0,
            "wind_mean": 5.0,
            "source": "fallback_defaults",
        }


def compute_doc(season_start: date | None, on_date: date | None = None) -> int:
    on_date = on_date or date.today()
    if not season_start:
        return 1
    doc = (on_date - season_start).days + 1
    return max(1, min(int(doc), 200))


def harvest_scale(initial_stocks: float | None, current_stocks: float | None) -> float:
    """Scale feed down as shrimp count declines (harvest / mortality)."""
    if not initial_stocks or initial_stocks <= 0:
        return 1.0
    if current_stocks is None:
        return 1.0
    ratio = float(current_stocks) / float(initial_stocks)
    return float(max(0.15, min(1.0, ratio)))


def growth_biomass_scale(current_count: float | None, abw_g: float | None) -> dict[str, float]:
    """
    Scale feed by live Growth Dashboard biomass vs a training-like reference.

    More shrimp or heavier ABW → higher feed.
    Fewer / lighter → lower feed (so you can see adjustment when Growth changes).

    The base ML model was trained on a limited range of stocking counts, so it
    plateaus (stops changing) once "stocks" goes past what it saw in training —
    this scale is what keeps the *total* feed responsive beyond that point.
    A hard clip here would recreate the same flatlining problem, so above the
    reference biomass the scale keeps climbing (log-dampened so it doesn't
    explode) instead of pinning at a fixed ceiling.
    """
    count = max(0.0, float(current_count or 0))
    abw = max(0.1, float(abw_g or 1.0))
    cur_biomass = count * abw  # gram-biomass proxy
    ref_biomass = REF_STOCKS * REF_ABW_G
    raw = cur_biomass / ref_biomass if ref_biomass > 0 else 1.0
    if raw <= 1.0:
        scale = max(0.08, raw)
    else:
        # Continuous at raw=1 (scale=1), then grows without a hard ceiling.
        scale = 1.0 + math.log(raw)
    scale = float(scale)
    return {
        "growth_scale": scale,
        "biomass_g": round(cur_biomass, 1),
        "ref_biomass_g": ref_biomass,
        "shrimp_count": count,
        "abw_g": abw,
        "stock_vs_ref": round(count / REF_STOCKS, 4) if REF_STOCKS else 0.0,
        "abw_vs_ref": round(abw / REF_ABW_G, 4) if REF_ABW_G else 0.0,
    }


def recommend_feed(
    *,
    doc: int,
    weather: dict[str, float] | None = None,
    stocks: float = 0.0,
    density: float = 0.0,
    initial_stocks: float | None = None,
    current_stocks: float | None = None,
    abw_g: float | None = None,
) -> dict[str, Any]:
    bundle = _load_bundle()
    model = bundle["model"]
    feature_cols = bundle["feature_cols"]
    time_slots = bundle.get("time_slots") or ["06:00", "09:30", "13:00", "16:30", "19:00"]

    weather = weather or fetch_today_weather()
    live_count = float(current_stocks if current_stocks is not None else (stocks or 0))
    live_abw = float(abw_g if abw_g is not None and abw_g > 0 else 5.0)

    feats = {
        "doc": float(doc),
        "temp_mean": float(weather.get("temp_mean", 28)),
        "temp_max": float(weather.get("temp_max", 31)),
        "temp_min": float(weather.get("temp_min", 24)),
        "humidity_mean": float(weather.get("humidity_mean", 80)),
        "rain_sum": float(weather.get("rain_sum", 0)),
        "precip_sum": float(weather.get("precip_sum", 0)),
        "pressure_mean": float(weather.get("pressure_mean", 1010)),
        "cloud_mean": float(weather.get("cloud_mean", 50)),
        "wind_mean": float(weather.get("wind_mean", 5)),
        # Model feature: use live Growth Dashboard count when available
        "stocks": float(live_count or stocks or initial_stocks or 0),
        "density": float(density or 0),
    }
    x = np.array([[feats.get(c, 0.0) for c in feature_cols]], dtype=float)
    pred = model.predict(x)[0]
    pred = np.maximum(pred, 0.0)

    base_total = float(np.sum(pred))
    h_scale = harvest_scale(initial_stocks, live_count)
    g_info = growth_biomass_scale(live_count, live_abw)
    g_scale = g_info["growth_scale"]

    # Combine: stock decline * growth biomass (Growth Dashboard)
    combined = float(h_scale * g_scale)
    pred = pred * combined

    slots = {time_slots[i]: round(float(pred[i]), 2) for i in range(min(len(time_slots), len(pred)))}
    total = round(float(sum(slots.values())), 2)
    total_g = int(round(total * 1000))

    return {
        "unit": "kg",
        "doc": int(doc),
        "total_kg": total,
        "total_grams": total_g,
        "slots_kg": slots,
        "times": time_slots,
        "base_total_kg": round(base_total, 2),
        "harvest_scale": round(h_scale, 3),
        "growth_scale": round(g_scale, 3),
        "combined_scale": round(combined, 3),
        "growth": g_info,
        "weather": {k: weather.get(k) for k in (
            "temp_mean", "temp_max", "temp_min", "humidity_mean",
            "rain_sum", "precip_sum", "pressure_mean", "cloud_mean", "wind_mean", "source",
        )},
        "model_name": bundle.get("model_name"),
        "features_used": feats,
        "note": (
            "Scaled by Growth Dashboard shrimp count + average weight (biomass). "
            "Feed Once still uses your manual machine portion."
        ),
    }
