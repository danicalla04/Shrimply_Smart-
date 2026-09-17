/**
 * Phase 3: Prediction logging service
 * Stores weather forecasts with their ML corrections for later validation
 * Enables continuous model retraining and accuracy tracking
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export async function savePrediction(forecastData) {
  /**
   * Save a weather prediction for later validation
   *
   * @param {Object} forecastData - Forecast to save
   *   - location: string (required)
   *   - forecast_date: ISO datetime string (required)
   *   - metric: string (temperature, humidity, etc.) (required)
   *   - ensemble_value: number (required)
   *   - ml_corrected_value: number (required)
   *   - ensemble_confidence: number (0-100)
   *   - ml_confidence: number (0-100)
   *   - combined_confidence: number (0-100, optional - calculated)
   *   - open_meteo_value: number (optional)
   *   - weatherapi_value: number (optional)
   *   - nasa_value: number (optional)
   *
   * @returns {Object} Response with prediction_id if successful
   * @throws {Error} If save fails
   */

  try {
    const response = await fetch(`${API_BASE}/weather/save-prediction/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(forecastData),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || `Failed to save prediction: ${response.status}`);
    }

    const data = await response.json();
    return {
      success: true,
      prediction_id: data.prediction_id,
      timestamp: data.timestamp,
    };
  } catch (error) {
    console.error('[PredictionLogger] Error saving prediction:', error);
    throw error;
  }
}

export async function verifyPredictions(options = {}) {
  /**
   * Verify stored predictions against actual weather
   * Called daily to check forecast accuracy
   *
   * @param {Object} options - Query options
   *   - location: Filter by location
   *   - days: Number of days back (default: 1)
   *   - metric: Filter by metric
   *
   * @returns {Object} Verification results with accuracy metrics
   */

  try {
    const params = new URLSearchParams();
    if (options.location) params.append('location', options.location);
    if (options.days) params.append('days', options.days);
    if (options.metric) params.append('metric', options.metric);

    const response = await fetch(`${API_BASE}/weather/verify-predictions/?${params}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || `Failed to verify predictions: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('[PredictionLogger] Error verifying predictions:', error);
    throw error;
  }
}

export async function batchSavePredictions(forecasts) {
  /**
   * Save multiple predictions (one per metric)
   *
   * @param {Array} forecasts - Array of forecast objects
   *   Each: {location, forecast_date, metric, ensemble_value, ...}
   *
   * @returns {Array} Results for each saved prediction
   */

  const results = [];
  const errors = [];

  for (const forecast of forecasts) {
    try {
      const result = await savePrediction(forecast);
      results.push(result);
    } catch (error) {
      errors.push({
        metric: forecast.metric,
        error: error.message,
      });
    }
  }

  return {
    saved: results.length,
    failed: errors.length,
    results,
    errors,
  };
}

/**
 * Helper: Prepare forecast data from ensemble and ML correction results
 */
export function preparePredictionData(location, ensembleResult, mlCorrectionResult) {
  /**
   * Convert ensemble and ML results into prediction save format
   *
   * @param {string} location - Location name (e.g., "calapan")
   * @param {Object} ensembleResult - Result from ensembleForecaster.getEnsembleForecast()
   * @param {Object} mlCorrectionResult - Result from mlCorrection.applyMLCorrection()
   *
   * @returns {Array} Array of forecast objects ready to save
   */

  const forecasts = [];
  const now = new Date().toISOString();

  // Map ensemble metrics to predictions
  const metricMap = {
    temperature: 'temperature',
    humidity: 'humidity',
    wind_speed: 'wind_speed',
    rainfall: 'rainfall',
    pressure: 'pressure',
  };

  for (const [key, metric] of Object.entries(metricMap)) {
    if (ensembleResult.current && key in ensembleResult.current) {
      const ensembleVal = ensembleResult.current[key];
      const mlCorrected =
        mlCorrectionResult?.corrected_forecast?.[key] || ensembleVal;

      forecasts.push({
        location,
        forecast_date: now,
        metric,
        ensemble_value: ensembleVal,
        ml_corrected_value: mlCorrected,
        ensemble_confidence: ensembleResult.confidence,
        ml_confidence: mlCorrectionResult?.ml_confidence || 50,
        combined_confidence:
          mlCorrectionResult?.combined_confidence ||
          (0.6 * ensembleResult.confidence + 0.4 * 50),
        open_meteo_value: ensembleResult.current[`${key}_sources`]?.open_meteo,
        weatherapi_value: ensembleResult.current[`${key}_sources`]?.weatherapi,
        nasa_value: ensembleResult.current[`${key}_sources`]?.nasa,
      });
    }
  }

  return forecasts;
}

export default {
  savePrediction,
  verifyPredictions,
  batchSavePredictions,
  preparePredictionData,
};
