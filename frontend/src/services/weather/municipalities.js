/**
 * Municipality API Service
 * Manages all API calls related to Oriental Mindoro municipalities
 */

import { EFFECTIVE_API_BASE } from '../apiConfig';

/**
 * Fetch all 15 Oriental Mindoro municipalities
 * @returns {Promise<Array>} Array of municipalities with metadata
 */
export async function fetchMunicipalities() {
  try {
    const response = await fetch(`${EFFECTIVE_API_BASE}/weather/locations/?detailed=true`);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: Failed to fetch municipalities`);
    }
    
    const data = await response.json();
    return data.municipalities || [];
  } catch (error) {
    console.error('[municipalities] Failed to fetch:', error);
    throw error;
  }
}

/**
 * Switch active municipality for weather forecast
 * @param {string} location - Municipality key (e.g., 'calapan', 'puerto_galera')
 * @returns {Promise<Object>} Updated location info
 */
export async function setActiveMunicipality(location) {
  try {
    const response = await fetch(`${EFFECTIVE_API_BASE}/weather/locations/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        location,
        include_ml_info: true,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: Failed to set municipality`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('[municipalities] Failed to set active municipality:', error);
    throw error;
  }
}

/**
 * Get forecast for specific municipality (Calapan City - HIGH ACCURACY)
 * @param {number} days - Number of days (1-14, default 7)
 * @returns {Promise<Object>} Calapan forecast with ML confidence
 */
export async function getCalapanForecast(days = 7) {
  try {
    const response = await fetch(
      `${EFFECTIVE_API_BASE}/weather/calapan/?days=${days}&include_confidence=true`,
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: Failed to get Calapan forecast`);
    }

    return await response.json();
  } catch (error) {
    console.error('[municipalities] Failed to get Calapan forecast:', error);
    throw error;
  }
}

/**
 * Get forecast for any municipality
 * @param {string} municipality - Municipality key (e.g., 'puerto_galera')
 * @param {number} days - Number of days (1-14, default 7)
 * @returns {Promise<Object>} Municipality forecast with metadata
 */
export async function getMunicipalityForecast(municipality, days = 7) {
  try {
    const response = await fetch(
      `${EFFECTIVE_API_BASE}/weather/municipality/?municipality=${municipality}&days=${days}&include_ml_confidence=true`,
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: Failed to get municipality forecast`);
    }

    return await response.json();
  } catch (error) {
    console.error('[municipalities] Failed to get municipality forecast:', error);
    throw error;
  }
}

/**
 * Get ML accuracy report for municipalities
 * @param {string} municipality - Optional: Filter by specific municipality
 * @param {string} metric - Optional: Filter by specific metric (temperature, humidity, etc.)
 * @returns {Promise<Object>} Accuracy metrics and statistics
 */
export async function getMunicipalityAccuracyReport(municipality = null, metric = null) {
  try {
    let url = `${EFFECTIVE_API_BASE}/weather/ml-accuracy/`;
    const params = new URLSearchParams();

    if (municipality) params.append('municipality', municipality);
    if (metric) params.append('metric', metric);

    if (params.toString()) {
      url += `?${params.toString()}`;
    }

    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: Failed to get accuracy report`);
    }

    return await response.json();
  } catch (error) {
    console.error('[municipalities] Failed to get accuracy report:', error);
    throw error;
  }
}

/**
 * Convert municipality object to location format
 * Used to integrate with existing WeatherLayout location system
 * @param {Object} municipality - Municipality object from API
 * @returns {Object} Location object compatible with WeatherLayout
 */
export function municipalityToLocation(municipality) {
  return {
    name: municipality.display_name,
    admin1: 'Oriental Mindoro',
    country: 'Philippines',
    latitude: municipality.coordinates.latitude,
    longitude: municipality.coordinates.longitude,
    timezone: 'Asia/Manila',
    _metadata: {
      municipalityKey: municipality.key,
      isPrimary: municipality.is_primary,
      isCoastal: municipality.is_coastal,
      elevation: municipality.elevation_m,
      modelAvailable: municipality.model_available || false,
    },
  };
}

/**
 * Find municipality by coordinates
 * @param {number} latitude
 * @param {number} longitude
 * @returns {Promise<Object>} Nearest municipality
 */
export async function findNearestMunicipality(latitude, longitude) {
  try {
    const municipalities = await fetchMunicipalities();

    // Simple distance calculation
    const distances = municipalities.map((m) => {
      const dx = m.coordinates.latitude - latitude;
      const dy = m.coordinates.longitude - longitude;
      const distance = Math.sqrt(dx * dx + dy * dy);

      return { municipality: m, distance };
    });

    distances.sort((a, b) => a.distance - b.distance);
    return distances[0]?.municipality || municipalities[0];
  } catch (error) {
    console.error('[municipalities] Failed to find nearest municipality:', error);
    throw error;
  }
}
