/**
 * ML Correction Service
 * Sends ensemble forecasts to backend for ML-based corrections
 * Returns ensemble data enhanced with ML corrections and confidence scores
 */

const API_BASE = 'http://127.0.0.1:8000/api';
const ML_CORRECT_ENDPOINT = `${API_BASE}/weather/ensemble-correct/`;
const ML_INFO_ENDPOINT = `${API_BASE}/weather/ml-info/`;

const CACHE_DURATION = {
  mlInfo: 60 * 60 * 1000, // 1 hour
  mlCorrection: 30 * 60 * 1000, // 30 minutes
};

// In-memory cache for ML results
const mlCache = new Map();

const cache = {
  get: (key) => mlCache.get(key),
  set: (key, value) => mlCache.set(key, value),
};

/**
 * Apply ML corrections to ensemble forecast
 * 
 * @param {Object} ensembleForecast - Output from getEnsembleForecast()
 * @param {Object} options - { location?, historicalData?, signal? }
 * @returns {Promise<Object>} - ML-corrected forecast with confidence scores
 */
export async function applyMLCorrection(ensembleForecast, { location = 'calapan', historicalData = null, signal } = {}) {
  try {
    if (!ensembleForecast) {
      throw new Error('ensembleForecast is required');
    }

    // Check cache first
    const cacheKey = `ml_correction_${location}`;
    const cached = cache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < CACHE_DURATION.mlCorrection) {
      console.log('[ML] Using cached correction');
      return cached.data;
    }

    // Call backend ML correction endpoint
    const response = await fetch(ML_CORRECT_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ensemble_forecast: ensembleForecast,
        location,
        historical_data: historicalData,
      }),
      signal,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`ML correction failed: ${response.status} - ${errorText}`);
    }

    const result = await response.json();
    
    // Cache the result
    cache.set(cacheKey, {
      data: result,
      timestamp: Date.now(),
    });

    console.log('[ML] Applied corrections:', result.corrections_applied?.length || 0, 'metrics');
    
    return result;
  } catch (error) {
    console.error('[ML] Correction error:', error.message);
    
    // Return ensemble forecast as fallback if ML correction fails
    if (error?.name === 'AbortError') throw error;
    
    return {
      corrected_forecast: ensembleForecast,
      ml_confidence: 0,
      corrections_applied: [],
      ml_models_active: { xgboost_count: 0, lstm_count: 0, correction_count: 0 },
      error: error.message,
    };
  }
}

/**
 * Get information about active ML models
 * 
 * @param {Object} options - { signal? }
 * @returns {Promise<Object>} - Model info including available models and libraries
 */
export async function getMLModelInfo({ signal } = {}) {
  try {
    // Check cache first
    const cacheKey = 'ml_model_info';
    const cached = cache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < CACHE_DURATION.mlInfo) {
      console.log('[ML] Using cached model info');
      return cached.data;
    }

    // Fetch from backend
    const response = await fetch(ML_INFO_ENDPOINT, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      signal,
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch ML model info: ${response.status}`);
    }

    const result = await response.json();
    
    // Cache the result
    cache.set(cacheKey, {
      data: result,
      timestamp: Date.now(),
    });

    console.log('[ML] Model info:', result.model_info);
    
    return result;
  } catch (error) {
    console.error('[ML] Model info error:', error.message);
    
    if (error?.name === 'AbortError') throw error;
    
    return {
      model_info: {
        xgboost_models: [],
        lstm_models: [],
        correction_models: [],
        models_available: { xgboost: 0, lstm: 0, corrections: 0 },
        libraries: { xgboost: false, tensorflow: false },
      },
      error: error.message,
    };
  }
}

/**
 * Check if ML models are available and functioning
 * 
 * @returns {Promise<boolean>} - True if at least one model type is available
 */
export async function isMLAvailable() {
  try {
    const info = await getMLModelInfo();
    const available = info.model_info?.models_available;
    return (available?.xgboost > 0) || (available?.lstm > 0) || (available?.corrections > 0);
  } catch {
    return false;
  }
}

/**
 * Calculate combined confidence score (ensemble + ML)
 * 
 * @param {Object} ensembleData - Ensemble forecast with confidence
 * @param {Object} mlResult - ML correction result
 * @returns {number} - Combined confidence 0-100%
 */
export function calculateCombinedConfidence(ensembleData, mlResult) {
  const ensembleConfidence = ensembleData?.confidence || 0;
  const mlConfidence = mlResult?.ml_confidence || 0;
  
  // Weight ensemble 60%, ML 40%
  return (ensembleConfidence * 0.6) + (mlConfidence * 0.4);
}

/**
 * Get corrected forecast value with fallback
 * 
 * @param {Object} mlResult - ML correction result
 * @param {string} metric - 'temperature', 'humidity', etc.
 * @param {string} type - 'current', 'daily', 'hourly'
 * @param {number} index - Index for daily/hourly (optional)
 * @returns {number} - Corrected value or original if not available
 */
export function getCorrectedValue(mlResult, metric, type = 'current', index = 0) {
  try {
    const forecast = mlResult?.corrected_forecast;
    
    if (type === 'current' && forecast?.current) {
      const key = `${metric}_corrected`;
      return forecast.current[key] ?? forecast.current[metric];
    }
    
    if (type === 'daily' && forecast?.daily?.[index]) {
      const key = `${metric}_corrected`;
      return forecast.daily[index][key] ?? forecast.daily[index][metric];
    }
    
    if (type === 'hourly' && forecast?.hourly?.[index]) {
      const key = `${metric}_corrected`;
      return forecast.hourly[index][key] ?? forecast.hourly[index][metric];
    }
    
    return null;
  } catch {
    return null;
  }
}

/**
 * Get ML confidence for specific metric
 * 
 * @param {Object} mlResult - ML correction result
 * @param {string} metric - 'temperature', 'humidity', etc.
 * @returns {number} - Confidence 0-1 or null if not available
 */
export function getMetricMLConfidence(mlResult, metric) {
  try {
    const current = mlResult?.corrected_forecast?.current;
    if (current) {
      const key = `${metric}_ml_confidence`;
      return current[key] ?? null;
    }
    return null;
  } catch {
    return null;
  }
}

export default {
  applyMLCorrection,
  getMLModelInfo,
  isMLAvailable,
  calculateCombinedConfidence,
  getCorrectedValue,
  getMetricMLConfidence,
};
