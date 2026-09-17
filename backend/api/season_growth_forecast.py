"""
Season growth forecast for Reports.

Builds a daily feature table (DOC, feed, weather, water quality, observed ABW)
and projects day-by-day ABW / harvest kg using the sampling ADG model plus
simple weather / WQ modifiers.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DATASET_ROOT = Path(__file__).resolve().parents[2] / "dataset"
SAMPLING_CSV = DATASET_ROOT / "data" / "growth_sampling_training.csv"

TARGET_HARVEST_ABW_G = 18.0
DEFAULT_START_ABW_G = 0.8
DEFAULT_ADG = 0.18


@lru_cache(maxsize=1)
def _load_sampling_rows():
    if not SAMPLING_CSV.exists():
        return []
    try:
        df = pd.read_csv(SAMPLING_CSV)
    except Exception as exc:
        logger.warning("Failed to read sampling CSV: %s", exc)
        return []
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    out = []
    for _, r in df.iterrows():
        d = r["date"].date() if pd.notna(r["date"]) else None
        abw = pd.to_numeric(r.get("abw_g"), errors="coerce")
        if d is None or pd.isna(abw):
            continue
        out.append({
            "date": d,
            "batch": str(r.get("batch") or ""),
            "doc": int(pd.to_numeric(r.get("doc"), errors="coerce") or 0),
            "abw_g": float(abw),
            "adg_g": float(pd.to_numeric(r.get("adg_g"), errors="coerce") or 0) or None,
            "lf_kg": float(pd.to_numeric(r.get("lf_kg"), errors="coerce") or 0) or None,
            "sr_pct": float(pd.to_numeric(r.get("sr_pct"), errors="coerce") or 0) or None,
            "bio_kg": float(pd.to_numeric(r.get("bio_kg"), errors="coerce") or 0) or None,
            "initial_stock_pcs": int(pd.to_numeric(r.get("initial_stock_pcs"), errors="coerce") or 0) or None,
        })
    return out


def _parse_day(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except Exception:
        return None


def _wq_class(temp, ph, tds, turbidity):
    """Best-effort ML water-quality class; None if inputs insufficient."""
    try:
        from .ml_water_quality import predict_water_quality
        res = predict_water_quality(
            temperature=temp, ph=ph, tds=tds, turbidity=turbidity,
        )
        return (res or {}).get("ml_class")
    except Exception:
        return None


def _adg_modifier(weather_temp, precip, wq_class, ph, turbidity):
    """
    Scale ADG by weather / WQ stress (1.0 = no change).
    Kept conservative so feed+DOC model remains primary.
    """
    mod = 1.0
    if weather_temp is not None:
        if weather_temp < 24 or weather_temp > 34:
            mod *= 0.80
        elif weather_temp < 26 or weather_temp > 32:
            mod *= 0.90
    if precip is not None and precip >= 20:
        mod *= 0.88
    elif precip is not None and precip >= 10:
        mod *= 0.94

    if wq_class == "Severe":
        mod *= 0.70
    elif wq_class == "Warning":
        mod *= 0.82
    elif wq_class == "Caution":
        mod *= 0.92

    # Threshold stress when pond sensors present
    if ph is not None and (ph < 6.5 or ph > 9.0):
        mod *= 0.85
    if turbidity is not None and turbidity > 100:
        mod *= 0.90

    return float(np.clip(mod, 0.45, 1.15))


def _predict_adg_for_day(predictor, doc, abw_g, lf_kg, initial_stock, sr_pct):
    """Use sampling ADG model when available."""
    if predictor is None or predictor.model is None:
        return DEFAULT_ADG, "fallback-default-adg"

    feats = predictor.feature_names or [
        "doc", "abw_g", "lf_kg", "initial_stock_pcs", "sr_pct",
    ]
    medians = predictor.impute_medians or {}
    feature_map = {
        "doc": float(doc),
        "abw_g": float(abw_g),
        "lf_kg": float(lf_kg if lf_kg is not None else medians.get("lf_kg", 80.0)),
        "initial_stock_pcs": float(initial_stock or medians.get("initial_stock_pcs", 250000)),
        "sr_pct": float(sr_pct if sr_pct is not None else medians.get("sr_pct", 75.0)),
    }

    # Prefer sampling/DOC model; otherwise fall back to mean ADG
    if predictor.model_family == "sampling_growth_v1" or "doc" in feats:
        row = [float(feature_map.get(n, medians.get(n, 0.0))) for n in feats]
        X = np.array([row], dtype=float)
        try:
            X = pd.DataFrame(X, columns=list(feats))
        except Exception:
            pass
        try:
            if predictor.scaler is not None and not hasattr(predictor.model, "named_steps"):
                X = predictor.scaler.transform(X)
            adg = float(predictor.model.predict(X)[0])
            adg = float(np.clip(adg, 0.05, 1.2))
            return adg, (predictor.bundle or {}).get("model_version") or "sampling-adg-v1"
        except Exception as exc:
            logger.debug("ADG predict failed: %s", exc)

    mean_adg = getattr(predictor, "mean_adg", None) or DEFAULT_ADG
    return float(np.clip(mean_adg, 0.05, 1.2)), "mean-adg-fallback"


def build_observed_abw_map(season, start_d, end_d):
    """Observed ABW from DB growth metrics + sampling CSV overlapping the season."""
    observed = {}

    if season is not None:
        for m in season.growth_metrics.filter(date__gte=start_d, date__lte=end_d).order_by("date"):
            if m.avg_weight_grams is not None:
                observed[m.date] = {
                    "abw_g": float(m.avg_weight_grams),
                    "source": "growth_metric",
                    "adg_g": float(m.daily_weight_gain_grams or 0) or None,
                }

    for row in _load_sampling_rows():
        d = row["date"]
        if start_d <= d <= end_d:
            # Prefer DB metric if already present
            if d not in observed:
                observed[d] = {
                    "abw_g": row["abw_g"],
                    "source": f"sampling:{row['batch']}",
                    "adg_g": row["adg_g"],
                }
    return observed


def build_season_growth_forecast(season, daily_rows, start_d=None, end_d=None):
    """
    Returns dict:
      feature_table, abw_series, predicted_harvest_kg, recommendations, meta
    """
    if season is None:
        return None

    start_d = start_d or season.start_date
    end_d = end_d or season.end_date or date.today()
    if not start_d or end_d < start_d:
        return None

    by_day = {}
    for r in daily_rows or []:
        d = _parse_day(r.get("date"))
        if d:
            by_day[d] = r

    observed = build_observed_abw_map(season, start_d, end_d)

    initial_stock = int(
        getattr(season, "initial_shrimp_quantity", 0)
        or season.stocking_density
        or 250000
    )
    current_stock = int(
        getattr(season, "current_shrimp_quantity", 0) or initial_stock
    )
    final_abw_known = getattr(season, "average_shrimp_weight_grams", None)
    actual_harvest_kg = float(getattr(season, "total_harvest_kg", 0) or 0) or None

    try:
        from .ml_shrimp_growth import ShrimpGrowthPredictor
        predictor = ShrimpGrowthPredictor()
    except Exception:
        predictor = None

    # Seed ABW
    first_obs = min(observed.keys()) if observed else None
    if first_obs and first_obs == start_d:
        abw = observed[first_obs]["abw_g"]
    elif first_obs and (first_obs - start_d).days <= 35:
        # Back-extrapolate roughly from first sampling
        gap = (first_obs - start_d).days
        abw = max(DEFAULT_START_ABW_G, observed[first_obs]["abw_g"] - DEFAULT_ADG * gap)
    else:
        abw = DEFAULT_START_ABW_G

    feature_table = []
    abw_series = []
    model_version = "n/a"
    mods_used = []

    day = start_d
    while day <= end_d:
        doc = (day - start_d).days
        row = by_day.get(day, {})
        feed_kg = row.get("feed_kg")
        w_temp = row.get("weather_temperature")
        precip = row.get("weather_precipitation_mm")
        humidity = row.get("weather_humidity")
        w_cond = row.get("weather_condition")
        pond_temp = row.get("avg_temperature")
        ph = row.get("avg_ph")
        turb = row.get("avg_turbidity")
        tds = row.get("avg_tds")

        # Survival drifts gently if no metric (same idea as growth predictions)
        sr_pct = (current_stock / initial_stock * 100.0) if initial_stock else 75.0
        sr_pct = max(40.0, sr_pct - 0.03 * doc)

        wq_class = None
        if pond_temp is not None or ph is not None or tds is not None or turb is not None:
            wq_class = _wq_class(pond_temp, ph, tds, turb)

        base_adg, model_version = _predict_adg_for_day(
            predictor, doc, abw, feed_kg, initial_stock, sr_pct,
        )
        mod = _adg_modifier(w_temp, precip, wq_class, ph, turb)
        if feed_kg is not None and feed_kg < 5 and doc > 20:
            mod *= 0.90  # very low feed mid-culture
        adg = float(np.clip(base_adg * mod, 0.03, 1.2))
        if abs(mod - 1.0) > 0.02:
            mods_used.append(mod)

        obs = observed.get(day)
        abw_observed = obs["abw_g"] if obs else None
        if abw_observed is not None:
            abw = abw_observed  # snap to sampling
            adg_used = obs.get("adg_g") or adg
        else:
            abw = max(0.1, abw + adg)
            adg_used = adg

        # Biomass estimate (kg)
        live_count = int(initial_stock * (sr_pct / 100.0))
        biomass_kg = round(abw * live_count / 1000.0, 2)

        feature_table.append({
            "date": day.isoformat(),
            "doc": doc,
            "feed_kg": round(float(feed_kg), 2) if feed_kg is not None else None,
            "weather_temperature": w_temp,
            "weather_precipitation_mm": precip,
            "weather_humidity": humidity,
            "weather_condition": w_cond,
            "wq_temperature": pond_temp,
            "wq_ph": ph,
            "wq_turbidity": turb,
            "wq_tds": tds,
            "wq_class": wq_class,
            "abw_observed": abw_observed,
            "abw_predicted": round(abw, 3),
            "adg_predicted": round(adg_used, 3),
            "adg_modifier": round(mod, 3),
            "biomass_kg_predicted": biomass_kg,
            "sr_pct": round(sr_pct, 1),
        })
        abw_series.append({
            "date": day.isoformat(),
            "doc": doc,
            "abw_predicted": round(abw, 3),
            "abw_observed": abw_observed,
            "biomass_kg_predicted": biomass_kg,
        })
        day += timedelta(days=1)

    # Optional calibration toward known end ABW (ended seasons)
    if final_abw_known and feature_table:
        pred_end = feature_table[-1]["abw_predicted"]
        if pred_end and pred_end > 0 and abs(pred_end - float(final_abw_known)) / pred_end > 0.08:
            scale = float(final_abw_known) / pred_end
            # Soft calibration — pull curve halfway toward known end weight
            blend = 0.5 * scale + 0.5
            for i, ft in enumerate(feature_table):
                if ft["abw_observed"] is None:
                    ft["abw_predicted"] = round(ft["abw_predicted"] * blend, 3)
                    ft["biomass_kg_predicted"] = round(
                        ft["abw_predicted"] * initial_stock * (ft["sr_pct"] / 100.0) / 1000.0, 2
                    )
                abw_series[i]["abw_predicted"] = ft["abw_predicted"]
                abw_series[i]["biomass_kg_predicted"] = ft["biomass_kg_predicted"]
            abw = feature_table[-1]["abw_predicted"]

    final_sr = feature_table[-1]["sr_pct"] if feature_table else 70.0
    live_count = int(initial_stock * (final_sr / 100.0))
    predicted_harvest_kg = round(abw * live_count / 1000.0, 2)

    # Days to target harvest weight from last day
    last_adg = feature_table[-1]["adg_predicted"] if feature_table else DEFAULT_ADG
    if abw < TARGET_HARVEST_ABW_G and last_adg > 0:
        days_to_target = int(np.ceil((TARGET_HARVEST_ABW_G - abw) / last_adg))
        est_harvest_date = (end_d + timedelta(days=days_to_target)).isoformat()
    else:
        days_to_target = 0
        est_harvest_date = end_d.isoformat()

    recommendations = _build_recommendations(
        feature_table, predicted_harvest_kg, actual_harvest_kg, final_abw_known,
    )

    avg_mod = float(np.mean(mods_used)) if mods_used else 1.0
    return {
        "feature_table": feature_table,
        "abw_series": abw_series,
        "predicted_harvest_kg": predicted_harvest_kg,
        "actual_harvest_kg": actual_harvest_kg,
        "final_abw_g": round(abw, 3),
        "target_abw_g": TARGET_HARVEST_ABW_G,
        "days_to_target_abw": days_to_target,
        "estimated_harvest_date": est_harvest_date,
        "initial_stock": initial_stock,
        "recommendations": recommendations,
        "meta": {
            "model_version": model_version,
            "days": len(feature_table),
            "sampling_points": len(observed),
            "avg_environment_modifier": round(avg_mod, 3),
            "sources": [
                "feedOfSrimpDateAndAmount / daily_rows",
                "weatherForShrimpFeedingDate / daily_rows",
                "SensorReading (when present)",
                "growth_sampling_training.csv / DailyGrowthMetric",
                "growth_predictor_v1.pkl (ADG)",
            ],
        },
    }


def _build_recommendations(feature_table, predicted_harvest_kg, actual_harvest_kg, final_abw_known):
    recs = []
    if not feature_table:
        return [{"type": "info", "message": "Not enough daily data to build growth recommendations."}]

    low_feed_days = sum(
        1 for r in feature_table
        if r.get("feed_kg") is not None and r["feed_kg"] < 8 and r["doc"] > 25
    )
    heavy_rain = sum(1 for r in feature_table if (r.get("weather_precipitation_mm") or 0) >= 20)
    caution_wq = sum(1 for r in feature_table if r.get("wq_class") in ("Caution", "Warning", "Severe"))
    bad_ph = sum(
        1 for r in feature_table
        if r.get("wq_ph") is not None and (r["wq_ph"] < 6.5 or r["wq_ph"] > 9)
    )
    slow_days = sum(1 for r in feature_table if (r.get("adg_modifier") or 1) < 0.9)
    avg_adg = float(np.mean([r["adg_predicted"] for r in feature_table if r.get("adg_predicted")]))
    final_abw = feature_table[-1]["abw_predicted"]

    if low_feed_days >= 5:
        recs.append({
            "type": "warning",
            "message": f"Increase feed: {low_feed_days} mid/late-culture day(s) with feed < 8 kg — growth may stall.",
        })
    if heavy_rain >= 5:
        recs.append({
            "type": "warning",
            "message": f"Heavy rain on {heavy_rain} day(s) — expect slower growth; check turbidity and reduce stress after storms.",
        })
    if caution_wq or bad_ph:
        recs.append({
            "type": "critical" if bad_ph >= 3 or caution_wq >= 3 else "warning",
            "message": (
                "WQ caution → slower growth: "
                f"{caution_wq} ML-flagged day(s), {bad_ph} day(s) with pH outside 6.5–9. "
                "Correct water quality before pushing feed."
            ),
        })
    if slow_days >= max(5, len(feature_table) // 5):
        recs.append({
            "type": "info",
            "message": f"Environment modifiers reduced ADG on {slow_days} day(s) (avg ADG ~{avg_adg:.2f} g/day).",
        })
    if final_abw < TARGET_HARVEST_ABW_G:
        recs.append({
            "type": "info",
            "message": (
                f"Projected ABW {final_abw:.1f} g is below target {TARGET_HARVEST_ABW_G:.0f} g. "
                f"Predicted biomass ~{predicted_harvest_kg:.0f} kg."
            ),
        })
    else:
        recs.append({
            "type": "info",
            "message": (
                f"Projected ABW {final_abw:.1f} g meets harvest size. "
                f"Predicted biomass ~{predicted_harvest_kg:.0f} kg."
            ),
        })
    if actual_harvest_kg and predicted_harvest_kg:
        delta = predicted_harvest_kg - actual_harvest_kg
        recs.append({
            "type": "info",
            "message": (
                f"Model vs actual harvest: predicted {predicted_harvest_kg:.0f} kg vs "
                f"actual {actual_harvest_kg:.0f} kg (Δ {delta:+.0f} kg)."
            ),
        })
    if final_abw_known:
        recs.append({
            "type": "info",
            "message": f"Season recorded average weight {final_abw_known} g used to soft-calibrate the curve.",
        })
    if not recs:
        recs.append({"type": "info", "message": "Growth trajectory looks stable — maintain current feed and WQ management."})
    return recs
