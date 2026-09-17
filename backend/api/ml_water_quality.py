"""
Water-quality multiclass classifier (Normal / Caution / Warning / Severe).

Trained from dataset/water/fishpond_dataset_multiclass_2153.csv
Served via backend/api/ml_models/water_quality_classifier_v1.pkl
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "ml_models"
MODEL_PATH = MODEL_DIR / "water_quality_classifier_v1.pkl"

_BUNDLE = None


def load_water_quality_model(force=False):
    global _BUNDLE
    if _BUNDLE is not None and not force:
        return _BUNDLE
    if not MODEL_PATH.exists():
        logger.warning("Water quality model not found at %s", MODEL_PATH)
        _BUNDLE = None
        return None
    try:
        with open(MODEL_PATH, "rb") as f:
            _BUNDLE = pickle.load(f)
        logger.info("Loaded water quality classifier from %s", MODEL_PATH)
        return _BUNDLE
    except Exception as e:
        logger.error("Failed to load water quality model: %s", e)
        _BUNDLE = None
        return None


def _sanitize_sensor_value(key, value):
    """Drop physically impossible / probe-fail readings so ML is not fed junk."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if key == "ph" and (v < 1.0 or v > 14.0):
        return None  # pH 0 / >14 = broken probe, not real pond water
    if key == "temperature" and (v < 0.0 or v > 50.0):
        return None
    if key == "tds" and v < 0.0:
        return None
    if key == "turbidity" and v < 0.0:
        return None
    return v


def predict_water_quality(temperature=None, ph=None, tds=None, turbidity=None):
    """
    Predict class from live sensor values.

    Returns dict with ml_class, status, quality_score, confidence, probabilities
    or None if model unavailable / inputs insufficient.
    """
    bundle = load_water_quality_model()
    if not bundle or bundle.get("model") is None:
        return None

    feature_map = bundle.get("feature_map") or {
        "temperature": "temp_C",
        "ph": "pH",
        "tds": "tds_mgL",
        "turbidity": "turbidity_NTU",
    }
    features = bundle.get("features") or ["temp_C", "pH", "tds_mgL", "turbidity_NTU"]
    sensor_vals = {
        "temperature": _sanitize_sensor_value("temperature", temperature),
        "ph": _sanitize_sensor_value("ph", ph),
        "tds": _sanitize_sensor_value("tds", tds),
        "turbidity": _sanitize_sensor_value("turbidity", turbidity),
    }

    # Need all 4 live sensors — never invent missing TDS/pH from CSV medians
    # (that caused false "Normal ~78%" when probes were dead / reading 0).
    present = sum(1 for v in sensor_vals.values() if v is not None)
    if present < 4:
        return None

    row = []
    for feat in features:
        # reverse map: model feature → sensor key
        sensor_key = next((k for k, v in feature_map.items() if v == feat), None)
        val = sensor_vals.get(sensor_key) if sensor_key else None
        if val is None:
            return None
        row.append(float(val))

    X = np.array([row], dtype=float)
    try:
        import pandas as pd
        X = pd.DataFrame(X, columns=list(features))
    except Exception:
        pass
    model = bundle["model"]
    le = bundle.get("label_encoder")
    classes = bundle.get("classes") or ["Normal", "Caution", "Warning", "Severe"]
    status_map = bundle.get("status_map") or {
        "Normal": "good",
        "Caution": "caution",
        "Warning": "poor",
        "Severe": "poor",
    }
    score_map = bundle.get("score_map") or {
        "Normal": 100,
        "Caution": 70,
        "Warning": 40,
        "Severe": 15,
    }

    try:
        pred_idx = int(model.predict(X)[0])
        if le is not None:
            ml_class = str(le.inverse_transform([pred_idx])[0])
        else:
            ml_class = classes[pred_idx] if 0 <= pred_idx < len(classes) else str(pred_idx)

        probs = {}
        confidence = None
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X)[0]
            for i, p in enumerate(proba):
                if le is not None:
                    cname = str(le.inverse_transform([i])[0])
                else:
                    cname = classes[i] if i < len(classes) else str(i)
                probs[cname] = round(float(p) * 100, 1)
            confidence = round(float(max(proba)) * 100, 1)

        return {
            "ml_class": ml_class,
            "status": status_map.get(ml_class, "poor"),
            "quality_score": float(score_map.get(ml_class, 50)),
            "confidence": confidence,
            "probabilities": probs,
            "model_version": bundle.get("model_version", "water-quality-clf-v1"),
            "model_kind": bundle.get("model_kind"),
            "features_used": dict(zip(features, row)),
        }
    except Exception as e:
        logger.warning("Water quality predict failed: %s", e)
        return None
